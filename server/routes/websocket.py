#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/routes/websocket.py - Eventos WebSocket para comunicação em tempo real

import json
from flask import request
from flask_socketio import emit
from datetime import datetime
from core.config import config as server_config


def _automacao_ativada(status) -> bool:
    """Confirma que a automação terminou de subir: procura 'ativado' no texto
    do status (cobre Monitor ou Totem, e tolera pequenas variações de
    escrita) — nem exige a frase exata (frágil, nunca bate se o texto variar
    um pouco) nem aceita qualquer status que não seja 'parado' (frouxo
    demais: estados intermediários tipo 'Iniciando...' também não são
    'parado', mas a automação ainda não terminou de subir — usar esse
    critério fazia a contagem parar cedo demais, com tempos de uns 13s em vez
    dos ~60-90s reais)."""
    def _tem_ativado(texto):
        return isinstance(texto, str) and 'ativado' in texto.lower()

    if isinstance(status, dict):
        return _tem_ativado(status.get('monitor')) or _tem_ativado(status.get('totem'))
    return _tem_ativado(status)


def _agente_mede_rto(versao) -> bool:
    """True se o agente é ≥ 1.5.7 — versão em que o operador mede o RTO por
    conta própria (espera o painel ficar operacional antes de reportar) e manda
    o resultado + duracao_s corretos.

    Nesses, o servidor NÃO deve recontar o tempo: como o agente só envia o
    evento com o painel já 'ativado', a recontagem mediria apenas o intervalo
    evento→status (~2-3s) e sobrescreveria a duração real (ex.: 87s → 3s).
    Agentes antigos (que reportavam no início do reinício, ou mandavam durações
    absurdas) seguem com a medição feita pelo servidor.
    """
    try:
        partes = tuple(int(x) for x in str(versao).split('.')[:3])
        return partes >= (1, 5, 7)
    except (TypeError, ValueError, AttributeError):
        return False


def _classificar_saude(saude: dict) -> str:
    """Classifica o nível de saúde do operador com base nos thresholds configurados."""
    cfg = server_config.health
    ram  = saude.get('ram_pct')  or 0
    disk = saude.get('disco_pct') or 0
    temp = saude.get('temperatura') or 0

    if (ram  >= cfg.critico_ram  or
        disk >= cfg.critico_disco or
        (temp > 0 and temp >= cfg.critico_temperatura)):
        return 'Crítico'

    if (ram  >= cfg.atencao_ram  or
        disk >= cfg.atencao_disco or
        (temp > 0 and temp >= cfg.atencao_temperatura)):
        return 'Atenção'

    return 'Normal'


def _gerar_motivos_alerta(saude: dict, nivel: str) -> list:
    """Retorna lista de strings descrevendo os motivos do alerta."""
    if nivel == 'Normal':
        return []
    cfg = server_config.health
    motivos = []
    ram  = saude.get('ram_pct')  or 0
    disk = saude.get('disco_pct') or 0
    temp = saude.get('temperatura') or 0
    thr_ram  = cfg.critico_ram  if nivel == 'Crítico' else cfg.atencao_ram
    thr_disk = cfg.critico_disco if nivel == 'Crítico' else cfg.atencao_disco
    thr_temp = cfg.critico_temperatura if nivel == 'Crítico' else cfg.atencao_temperatura

    if ram >= thr_ram:
        motivos.append(f"Consumo de memória atingiu {ram:.0f}%.")
    if disk >= thr_disk:
        motivos.append(f"Disco com {disk:.0f}% de utilização.")
    if temp > 0 and temp >= thr_temp:
        motivos.append(f"Temperatura do equipamento está em {temp:.0f}°C.")
    return motivos


def register_websocket_handlers(socketio, db, connected_operators, logger, incident_detector=None):
    """Registra todos os handlers de eventos WebSocket.

    incident_detector (opcional): camada de monitoramento. Os handlers só o
    NOTIFICAM (chamadas rápidas, não-bloqueantes, à prova de exceção); toda a
    lógica pesada roda no worker do detector. Se for None, nada muda.
    """

    def _notificar(metodo, *args):
        """Notifica o detector sem jamais deixar um erro dele afetar o WebSocket."""
        if incident_detector is None:
            return
        try:
            getattr(incident_detector, metodo)(*args)
        except Exception:
            pass

    @socketio.on('connect')
    def handle_connect():
        """Manipula a conexão de um cliente WebSocket"""
        logger.info(f"Nova conexão WebSocket: {request.sid}")

    @socketio.on('registrar_operador')
    def handle_registrar_operador(data):
        """Registra um operador quando se conecta"""
        try:
            operador_id = data.get('id')
            nome = data.get('nome')
            
            if not operador_id:
                logger.warning(f"Tentativa de registro sem ID de operador: {request.sid}")
                emit('erro', {'mensagem': 'ID de operador não fornecido'})
                return
            
            # Verificar se o operador existe no banco de dados
            operador = db.get_operador(operador_id)
            
            # VERIFICAÇÃO DE OPERADOR DELETADO (SOFT DELETE)
            # Se o operador existe mas está marcado como deletado, enviar comando de RESET
            if operador and operador.get('deleted'):
                logger.warning(f"Operador {operador_id} tentou conectar mas está marcado como DELETADO. Enviando ordem de autodestruição.")
                emit('comando_reset', {'mensagem': 'Seu registro foi removido do servidor.'})
                return

            if not operador:
                # Se não existe, mas temos dados suficientes para criar (fluxo offline -> online), criamos
                if 'username' in data or 'username_monitor' in data: # Verifica se tem o minimo de dados de cadastro
                    logger.info(f"Operador {operador_id} desconhecido. Registrando automaticamente com dados fornecidos pelo cliente.")
                    try:
                        # Mapear dados do socket para o formato do banco
                        novo_operador = {
                            'nome': nome or f'Operador-{operador_id[:8]}',
                            'descricao': 'Registrado automaticamente via Client Offline',
                            'tipo_cadastro': data.get('tipo_cadastro', 'Monitor de Senhas'),
                            'username': data.get('username', ''),
                            'password': '', # Senha vem mascarada ou vazia por segurança? No client atual ela não é enviada no payload padrão de registro.
                            # Se a senha não vem, não conseguimos criar um registro funcional 100% se o client perder a config local.
                            # Mas para fins de gerenciamento, criamos o registro.
                            # TODO: O ideal seria o client enviar hash ou a senha segura na primeira conexão.
                            'usa_credenciais_separadas': data.get('usa_credenciais_separadas', False),
                            'username_monitor': data.get('username_monitor'),
                            'username_totem': data.get('username_totem')
                        }
                        
                        # Hack: Se o client não mandou senha (segurança), usamos um placeholder para permitir o insert NOT NULL
                        if not novo_operador['password']:
                            novo_operador['password'] = 'senha_placeholder_trocar_no_painel'
                            
                        # Precisamos forçar o ID que veio do client
                        # O método add_operador gera um novo UUID. Vamos criar um método especifico ou alterar add_operador?
                        # Vamos usar um método customizado aqui ou ajustar add_operador para aceitar ID opcional.
                        # Como não posso mudar assinatura fácil sem ver, vamos tentar inserir direto ou usar update se existir (mas não existe)
                        
                        # Ajuste no Database necessário: add_operador_with_id
                        # Por enquanto, vou assumir que o DB pode lidar ou vou chamar um update logo apos se falhar.
                        # Na verdade, vou alterar o database.py também para suportar 'id' no dicionario de dados.
                        
                        # Inserindo... (Assumindo que ajustarei database.py)
                        db.add_operador_with_id(operador_id, novo_operador)
                        operador = db.get_operador(operador_id)
                        
                    except Exception as e:
                        logger.error(f"Falha ao criar operador automaticamente: {e}")
                        emit('erro', {'mensagem': 'Falha ao registrar operador novo'})
                        return
                else:
                    logger.warning(f"Tentativa de registro com ID de operador inexistente e sem dados de cadastro: {operador_id}")
                    emit('erro', {'mensagem': 'Operador não encontrado e dados insuficientes para cadastro'})
                    return
            else:
                # Se já existe, atualiza as informações com o que veio do cliente (Sincronização).
                #
                # 'nome' fica de fora de propósito: é o admin quem define o
                # nome pelo painel do servidor, e esse é o dado autoritativo.
                # Incluir 'nome' aqui fazia o valor que o agente ainda tinha
                # em cache local (de antes de uma renomeação) sobrescrever o
                # banco a cada reconexão/heartbeat — a edição feita no painel
                # ficava "voltando" para o nome antigo.
                if 'tipo_cadastro' in data:
                    update_data = {
                        'tipo_cadastro': data.get('tipo_cadastro'),
                        'usa_credenciais_separadas': data.get('usa_credenciais_separadas'),
                        'username_monitor': data.get('username_monitor'),
                        'username_totem': data.get('username_totem'),
                        'username': data.get('username')
                    }
                    # Remove chaves None/Vazias para não apagar dados existentes
                    update_data = {k: v for k, v in update_data.items() if v is not None}
                    db.update_operador(operador_id, update_data)

            # Juntar o operador a uma sala específica para ele
            socketio.server.enter_room(request.sid, operador_id)
            
            # Metadados de monitoramento (versão do agente, voz e idioma).
            # Chegam no registro; guardamos em memória para o dashboard e
            # persistimos para aparecerem mesmo com o operador offline.
            versao = data.get('versao')
            voz = data.get('voz')
            idioma = data.get('idioma')

            # Registrar operador como conectado
            nome_operador = operador.get('nome') or nome or f'Operador-{operador_id[:8]}'
            connected_operators[operador_id] = {
                'sid': request.sid,
                'status': 'Conectado',
                'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ip': request.remote_addr,
                'versao': versao,
                'voz': voz,
                'idioma': idioma,
                'nome': nome_operador,
            }

            if versao or voz or idioma:
                db.atualizar_metadados_operador(operador_id, versao=versao, voz=voz, idioma=idioma)

            # Persiste o IP desta conexão — é o que sobrevive depois que o
            # operador cair, para a tela de detalhes mostrar o último IP
            # conhecido em vez de "N/A" quando ele está offline.
            db.atualizar_conexao_operador(operador_id, ip=request.remote_addr)

            logger.info(f"Operador registrado/sincronizado: {operador_id} - {nome_operador}"
                        + (f" (agente v{versao})" if versao else ""))

            # Enviar configurações atuais para o operador (Confirmar sync).
            # 'nome' vai junto para o agente poder atualizar o que exibe
            # localmente com o valor autoritativo do servidor, em vez de
            # ficar preso ao nome que tinha em cache antes de uma renomeação.
            emit('config_atualizada', {
                'username': operador['username'], # Retorna o que está no banco (pode ser placeholder se acabou de criar)
                'nome': nome_operador,
                'tipo_cadastro': operador.get('tipo_cadastro', 'Monitor de Senhas'),
                'usa_credenciais_separadas': operador.get('usa_credenciais_separadas')
            })
            
            # Notificar todos os clientes que o operador está online
            socketio.emit('status_operador', {
                'id': operador_id,
                'nome': nome_operador,
                'online': True,
                'status': 'Conectado',
                'ultima_atualizacao': connected_operators[operador_id]['ultima_atualizacao']
            })

            _notificar('notify_online', operador_id)
        except Exception as e:
            logger.error(f"Erro ao registrar operador: {str(e)}")
            emit('erro', {'mensagem': f'Erro ao registrar: {str(e)}'})

    @socketio.on('atualizar_status')
    def handle_atualizar_status(data):
        """Atualiza o status de um operador"""
        try:
            operador_id = data.get('id')
            if not operador_id:
                return

            if operador_id in connected_operators:
                # Atualizar os dados do operador conectado
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                connected_operators[operador_id]['ultima_atualizacao'] = now_str
                
                # Capturar e persistir dados de IP e Hostname
                current_ip = connected_operators[operador_id].get('ip')
                current_hostname = connected_operators[operador_id].get('system_info', {}).get('hostname')
                current_os = connected_operators[operador_id].get('system_info', {}).get('os')
                
                # Persistir no banco de dados SOMENTE se houver mudança de status ou periodicamente
                # Para evitar flood de logs/updates a cada 1s, verificamos se houve mudança real de dados críticos
                
                if 'status' in data:
                    connected_operators[operador_id]['status'] = data['status']

                    # Confirma um reinício pendente deste operador, se houver:
                    # é aqui — no primeiro status que confirmar a automação
                    # ativada, não no instante do próprio evento de reinício —
                    # que sabemos de verdade quanto tempo ela levou pra subir.
                    pendente = connected_operators[operador_id].get('reinicio_pendente')
                    if pendente and _automacao_ativada(data['status']):
                        duracao_s = int((datetime.now() - pendente['desde']).total_seconds())
                        db.finalizar_reinicio(pendente['evento_id'], 'sucesso', {
                            'fim': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'duracao_s': duracao_s,
                        })
                        del connected_operators[operador_id]['reinicio_pendente']
                        socketio.emit('eventos_atualizados', {'id': operador_id, 'novos': 1})

                    # Se o status mudou, aí sim atualizamos o banco para garantir sincronia, mas sem floodar o log se for só heartbeat
                    update_data = {
                        'last_ip': current_ip,
                        'last_hostname': current_hostname,
                        'last_os': current_os
                    }
                    # O update_operador gera log. Se chamarmos a cada segundo, inunda o log.
                    # Vamos atualizar silenciosamente ou apenas quando necessário.
                    # Idealmente: criar método update_heartbeat_data no DB que não gera log de auditoria
                    
                    # Por enquanto, para resolver o flood relatado, vamos evitar chamar db.update_operador a cada segundo
                    # Apenas atualizamos se realmente necessário (ex: status mudou) ou a cada X tempo
                    pass # A lógica de update no banco foi removida daqui para evitar o flood.
                
                if 'system_info' in data:
                    connected_operators[operador_id]['system_info'] = data['system_info']

                # Notificar todos os clientes sobre a atualização de status (Socket.IO é eficiente para isso)
                status_payload = {
                    'id': operador_id,
                    'nome': connected_operators[operador_id].get('nome'),
                    'online': True,
                    'status': connected_operators[operador_id].get('status'),
                    'hostname': connected_operators[operador_id].get('system_info', {}).get('hostname'),
                    'ultima_atualizacao': now_str,
                    'nivel_saude': connected_operators[operador_id].get('nivel_saude', 'Normal'),
                    'saude': connected_operators[operador_id].get('saude'),
                }
                socketio.emit('status_operador', status_payload)
                
                # Removido logger.debug para evitar flood em nível debug também se não for essencial
                # logger.debug(f"Status do operador {operador_id} atualizado para: {data.get('status')}")
        except Exception as e:
            logger.error(f"Erro ao atualizar status: {str(e)}")

    @socketio.on('solicitar_credenciais')
    def handle_solicitar_credenciais(data):
        """Envia as credenciais para um operador que as solicitou"""
        try:
            operador_id = data.get('operador_id')
            
            if not operador_id:
                logger.error("Solicitação de credenciais sem ID de operador")
                return
            
            logger.info(f"Operador {operador_id} solicitou credenciais")
            
            # Buscar operador no banco de dados
            operador = db.get_operador(operador_id)
            
            if not operador:
                logger.error(f"Operador não encontrado para envio de credenciais: {operador_id}")
                emit('erro', {'mensagem': 'Operador não encontrado'})
                return
            
            # Enviar credenciais para o operador
            emit('config_atualizada', {
                'username': operador.get('username', ''),
                'password': operador.get('password', ''),
                'codigo_maquina': operador.get('codigo_maquina', '')
            })
            
            logger.info(f"Credenciais enviadas para o operador {operador_id}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar credenciais para operador: {str(e)}")

    @socketio.on('saude_operador')
    def handle_saude_operador(data):
        """Recebe métricas de saúde do operador, classifica e transmite ao dashboard."""
        try:
            operador_id = data.get('id') or data.get('operator_id')
            if not operador_id or operador_id not in connected_operators:
                return

            saude = {
                'cpu_pct':    data.get('cpu_pct'),
                'ram_pct':    data.get('ram_pct'),
                'disco_pct':  data.get('disco_pct'),
                'temperatura': data.get('temperatura'),
                'timestamp':  data.get('timestamp', datetime.now().isoformat()),
            }

            nivel   = _classificar_saude(saude)
            motivos = _gerar_motivos_alerta(saude, nivel)

            connected_operators[operador_id]['saude']       = saude
            connected_operators[operador_id]['nivel_saude'] = nivel

            socketio.emit('saude_atualizada', {
                'id':      operador_id,
                'nome':    connected_operators[operador_id].get('nome'),
                'saude':   saude,
                'nivel':   nivel,
                'motivos': motivos,
            })
            logger.debug(
                f"Saúde do operador {operador_id}: "
                f"CPU={saude['cpu_pct']}% RAM={saude['ram_pct']}% "
                f"Disco={saude['disco_pct']}% Nivel={nivel}"
            )
        except Exception as e:
            logger.error(f"Erro ao processar saúde do operador: {e}")

    @socketio.on('evento_operador')
    def handle_evento_operador(data):
        """Recebe eventos de monitoramento do agente (reinícios e erros).

        O agente pode mandar um evento único ou um lote (lista em 'eventos').
        Persistimos e reemitimos ao dashboard para atualização ao vivo.
        """
        try:
            operador_id = data.get('id') or data.get('operator_id')
            if not operador_id:
                return

            eventos = data.get('eventos')
            if not isinstance(eventos, list):
                # evento único no próprio payload
                eventos = [data]

            gravados = 0
            for ev in eventos:
                tipo = ev.get('tipo')
                if tipo not in ('reinicio', 'erro'):
                    continue
                dados = ev.get('dados')
                nivel = ev.get('nivel')
                confia_agente = False   # agente ≥1.5.7 mede o RTO sozinho (definido abaixo)

                # Alimenta o detector de incidentes (não-bloqueante). Só o
                # reinício de 'Recuperação automática' e o erro de conexão do
                # Tasy interessam; o detector filtra o resto.
                if tipo == 'reinicio':
                    # O agente pode mandar mais de um evento pro MESMO
                    # reinício (ex.: um ao detectar/iniciar, outro ao concluir
                    # do lado dele). Se já existe um pendente deste operador,
                    # este evento é continuação — mescla os dados no registro
                    # existente em vez de abrir uma linha nova (isso já
                    # fragmentou um único reinício em duas linhas antes).
                    pendente = connected_operators.get(operador_id, {}).get('reinicio_pendente')
                    if pendente:
                        if dados:
                            db.mesclar_dados_reinicio(pendente['evento_id'], dados)
                        continue

                    # Agente ≥ 1.5.7 mede o RTO por conta própria e só reporta
                    # com o painel JÁ operacional: confiamos no resultado +
                    # duracao_s dele e NÃO recontamos no servidor (a recontagem
                    # mediria só o intervalo evento→status ~3s e sobrescreveria
                    # a duração real). Agente antigo: mantém a medição do servidor.
                    versao_ag = connected_operators.get(operador_id, {}).get('versao')
                    confia_agente = _agente_mede_rto(versao_ag) and nivel in ('sucesso', 'falha')

                    if not confia_agente:
                        # O servidor conta o tempo por conta própria — desde que
                        # recebeu este evento até confirmar que a automação
                        # ativou de verdade — porque o agente antigo não é
                        # confiável (já veio duração absurda, tipo 180min).
                        nivel = 'pendente'

                    # Se este reinício foi disparado pelo agendador do servidor
                    # (Configurações > Reinícios), o agente reporta o mesmo
                    # título genérico que usa para o comando manual do
                    # dashboard — os dois chegam nele como o mesmo evento de
                    # socket, sem distinção. O agendador marca a flag abaixo
                    # logo antes de emitir; aqui trocamos o rótulo antes de
                    # salvar, para o histórico não misturar as duas origens.
                    origem = connected_operators.get(operador_id, {}).pop('origem_comando_pendente', None)
                    if (origem and origem.get('origem') == 'agendado' and
                            (datetime.now() - origem['desde']).total_seconds() <= db.TIMEOUT_REINICIO_PENDENTE_S):
                        ev = dict(ev, titulo='Agendamento diário')
                        if isinstance(dados, dict):
                            dados = dict(dados, motivo='Agendamento diário')

                    _notificar('notify_reinicio', operador_id,
                               (dados or {}).get('motivo'))
                elif tipo == 'erro':
                    _notificar('notify_erro', operador_id,
                               ev.get('titulo'), ev.get('detalhe'))

                dados_json = json.dumps(dados, ensure_ascii=False) if dados is not None else None
                evento_id = db.registrar_evento(
                    operador_id,
                    tipo=tipo,
                    ocorrido_em=ev.get('ocorrido_em') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    nivel=nivel,
                    titulo=ev.get('titulo'),
                    detalhe=ev.get('detalhe'),
                    dados_json=dados_json)
                if evento_id:
                    gravados += 1
                    # Só marca 'pendente' (p/ o servidor recontar depois) quando
                    # NÃO confia no agente. Com agente ≥1.5.7 o evento já vem
                    # final (sucesso/falha + duracao_s real) e não deve ser
                    # sobrescrito por uma recontagem no handle_atualizar_status.
                    if (tipo == 'reinicio' and not confia_agente
                            and operador_id in connected_operators):
                        connected_operators[operador_id]['reinicio_pendente'] = {
                            'evento_id': evento_id,
                            'desde': datetime.now(),
                        }

            if gravados:
                # Avisa o dashboard que há eventos novos para este operador
                socketio.emit('eventos_atualizados', {'id': operador_id, 'novos': gravados})
                logger.debug(f"Eventos do operador {operador_id} gravados: {gravados}")
        except Exception as e:
            logger.error(f"Erro ao processar evento do operador: {e}")

    @socketio.on('disconnect')
    def handle_disconnect():
        """Manipula a desconexão de um cliente WebSocket"""
        try:
            # Encontrar qual operador está usando este sid
            operador_id = None
            for id, dados in connected_operators.items():
                if dados.get('sid') == request.sid:
                    operador_id = id
                    break
            
            if operador_id:
                # Se caiu com um reinício ainda pendente, ele nunca vai
                # confirmar — fecha como falha em vez de deixar "Iniciado"
                # parado pra sempre.
                pendente = connected_operators.get(operador_id, {}).get('reinicio_pendente')
                if pendente:
                    db.finalizar_reinicio(pendente['evento_id'], 'falha')
                    socketio.emit('eventos_atualizados', {'id': operador_id, 'novos': 1})

                # Remover operador da lista de conectados
                nome_operador = connected_operators.get(operador_id, {}).get('nome')
                connected_operators.pop(operador_id, None)

                # Notificar todos os clientes que o operador está offline
                socketio.emit('status_operador', {
                    'id': operador_id,
                    'nome': nome_operador,
                    'online': False
                })

                _notificar('notify_offline', operador_id)
                logger.info(f"Operador desconectado: {operador_id}")
        except Exception as e:
            logger.error(f"Erro ao processar desconexão: {str(e)}")

    @socketio.on('heartbeat')
    def handle_heartbeat(data):
        """Manipula eventos de heartbeat para manter a conexão ativa"""
        try:
            operador_id = data.get('id')
            
            if not operador_id:
                return
            
            # Verificar se o operador existe nos conectados
            if operador_id in connected_operators:
                # Atualizar timestamp de último contato
                connected_operators[operador_id]['ultima_atualizacao'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"Heartbeat recebido do operador {operador_id}")
                
                # Responder com um ack para manter a conexão bidirecional
                emit('heartbeat_ack', {'timestamp': datetime.now().isoformat()})
            else:
                # Se o operador não está na lista, pode ter sido desconectado
                # Vamos tentar readicionar se ele existir no banco de dados
                operador = db.get_operador(operador_id)
                if operador:
                    logger.info(f"Operador {operador_id} reconectado via heartbeat")

                    # Adicionar novamente à lista de conectados
                    nome_operador = operador.get('nome') or f'Operador-{operador_id[:8]}'
                    connected_operators[operador_id] = {
                        'sid': request.sid,
                        'status': 'Reconectado',
                        'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'ip': request.remote_addr,
                        'nome': nome_operador,
                    }
                    db.atualizar_conexao_operador(operador_id, ip=request.remote_addr)

                    # Juntar à sala novamente
                    socketio.server.enter_room(request.sid, operador_id)

                    # Notificar todos os clientes que o operador está online novamente
                    socketio.emit('status_operador', {
                        'id': operador_id,
                        'nome': nome_operador,
                        'online': True,
                        'status': 'Reconectado',
                        'ultima_atualizacao': connected_operators[operador_id]['ultima_atualizacao']
                    })
                    
                    # Responder com um ack
                    emit('heartbeat_ack', {'timestamp': datetime.now().isoformat()})
                else:
                    logger.warning(f"Heartbeat recebido de operador desconhecido: {operador_id}")
        except Exception as e:
            logger.error(f"Erro ao processar heartbeat: {str(e)}")

    @socketio.on('comando_recebido')
    def handle_comando_recebido(data):
        """Recebe confirmação de recebimento de comando pelo operador"""
        try:
            operador_id = data.get('id')
            comando = data.get('comando')
            target = data.get('target')
            logger.info(f"✅ Operador {operador_id} confirmou recebimento do comando '{comando}' para '{target}'")
            # Pode-se emitir para o dashboard aqui se quiser feedback visual de "Recebido"
        except Exception as e:
            logger.error(f"Erro ao processar comando_recebido: {str(e)}")

    @socketio.on('comando_executado')
    def handle_comando_executado(data):
        """Recebe resultado da execução do comando"""
        try:
            operador_id = data.get('id')
            comando = data.get('comando')
            sucesso = data.get('sucesso')
            mensagem = data.get('mensagem')
            
            status_icon = "✅" if sucesso else "❌"
            logger.info(f"{status_icon} Operador {operador_id} finalizou comando '{comando}': {mensagem}")
            
            # Notificar dashboard (opcional, mas útil para toast notifications)
            socketio.emit('resultado_comando', {
                'id': operador_id,
                'comando': comando,
                'sucesso': sucesso,
                'mensagem': mensagem
            })
        except Exception as e:
            logger.error(f"Erro ao processar comando_executado: {str(e)}")

    return socketio