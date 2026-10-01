#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente principal do Operador Tasy - Refatorado para Multi-Automação
Versão: 1.5.5
"""

import time
import threading
import logging
import random
import getpass
from datetime import datetime
from typing import Optional, Dict
import schedule
import psutil

from core.config import OperadorConfig
from communication.websocket_client import WebSocketClient
from communication.server_api import ServerAPI
from automation.tasy_automation import TasyAutomation
from utils.constants import (
    STATUS_CONNECTED, STATUS_DISCONNECTED, STATUS_UPDATE_INTERVAL, 
    STATUS_ERROR, MAX_RECONNECTION_DELAY, AUTOMATION_MONITOR_INTERVAL,
    CADASTRO_MONITOR, CADASTRO_TOTEM, CADASTRO_AMBOS,
    TARGET_MONITOR, TARGET_TOTEM, TARGET_AMBOS,
    AUTOMATION_PORT_MONITOR, AUTOMATION_PORT_TOTEM,
    HOSTNAME, VERSION, RTO_TIMEOUT_S, RTO_POLL_S
)
from automation.voice_manager import DEFAULT_VOICE_NAME, DEFAULT_VOICE_LANG
from core.event_reporter import EventReporter, anexar_captura_de_erros
from utils.system_utils import (get_system_info, get_monitors_info, kill_edge_processes,
                                reset_application_data, resolve_monitor_indices)
from automation.browser_manager import EdgeBrowserManager
import sys
import os

logger = logging.getLogger("TasyOperador.Client")

class OperadorClient:
    """Cliente que coordena múltiplas instâncias de automação."""
    
    def __init__(self, config: OperadorConfig):
        self.config = config
        self.websocket: Optional[WebSocketClient] = None
        self.server_api: Optional[ServerAPI] = None
        self.automations: Dict[str, TasyAutomation] = {}
        self.automation_threads: Dict[str, threading.Thread] = {}
        self.automation_lock = threading.RLock()
        # Alvos com reinício em andamento, para absorver pedidos concorrentes.
        # _restart_lock é curto e nunca envolve I/O: protege apenas o conjunto.
        self._restart_lock = threading.Lock()
        self._restarting = set()
        self.running = False
        self.status = STATUS_DISCONNECTED
        self._setup_components()

        # Repórter de eventos de monitoramento (reinícios e erros). Camada
        # isolada: só observa e envia, nunca interfere na automação. Ver
        # core/event_reporter.py.
        self.event_reporter = EventReporter(
            ws_getter=lambda: self.websocket,
            id_getter=self.config.get_operator_id,
        )
        anexar_captura_de_erros(self.event_reporter)

        # Executar verificação e atualização do EdgeDriver UMA ÚNICA VEZ na inicialização
        self._ensure_edgedriver_ready()

    def _ensure_edgedriver_ready(self):
        """Garante que o EdgeDriver esteja atualizado e compatível antes de iniciar threads."""
        try:
            logger.info("🔧 Verificando compatibilidade do EdgeDriver...")
            manager = EdgeBrowserManager(self.config)
            manager.check_and_update_driver()
            logger.info("✅ EdgeDriver verificado e pronto para uso.")
        except Exception as e:
            logger.error(f"❌ Falha na verificação inicial do EdgeDriver: {e}", exc_info=True)
    
    def _setup_components(self):
        try:
            server_url = self.config.get_server_url()
            self.server_api = ServerAPI(server_url)
            self.websocket = WebSocketClient(server_url)
            self.websocket.set_command_callback(self._handle_command)
            self.websocket.set_config_update_callback(self._handle_config_update)
            self.websocket.set_reset_callback(self._handle_reset_command)
            self.websocket.set_connection_callbacks(self._on_websocket_connected, self._on_websocket_disconnected)
            logger.info("⚙️ Componentes do cliente (API, WebSocket) configurados.")
        except Exception as e:
            logger.error(f"Erro ao configurar componentes: {e}", exc_info=True)
            raise

    def _ensure_operator_registered(self) -> bool:
        """
        Garante que o operador tenha um ID/Nome local.
        Tenta conectar ao servidor, mas se falhar, permite operação offline se tiver config mínima.
        """
        if self.config.has_any_credentials():
            logger.info("✅ Configuração local válida encontrada. Iniciando em modo offline-first.")
            return True

        operator_id = self.config.get_operator_id()
        
        if operator_id:
            try:
                success, credentials, error = self.server_api.get_operator_credentials(operator_id)
                if success and credentials:
                    self.config.set_credentials('tasy_compartilhado', credentials.get('username'), credentials.get('password'))
                    self.config.set_tipo_cadastro(credentials.get('tipo_cadastro', 'Monitor de Senhas'))
                    self.config.save_config()
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Falha ao conectar ao servidor para buscar credenciais: {e}")

        # Tentar registrar interativamente no servidor se disponível
        try:
            # Teste simples de conexão antes de iniciar o fluxo interativo online
            if self.server_api.test_connection():
                 return self._register_operator()
        except:
            pass
            
        # Fallback Total: Operação Offline Local
        logger.warning("⚠️ Servidor indisponível e sem credenciais salvas.")
        return self._local_interactive_registration()

    def _local_interactive_registration(self) -> bool:
        """
        Solicita dados localmente para funcionar offline.
        Replica o formulário robusto do server_api.interactive_registration.
        """
        logger.info("📝 Iniciando configuração local (Offline Mode)...")
        print("\n" + "="*60)
        print("  🏥 REGISTRO DE OPERADOR LOCAL (OFFLINE) - PAINEL DE SENHAS HSV")
        print("="*60)
        print(f"  🖥️  Hostname: {HOSTNAME}")
        print("  ⚠️  Modo Offline: As configurações serão salvas apenas localmente.")
        print("="*60)
        
        try:
            # Gerar ID se não existir
            if not self.config.get_operator_id():
                import uuid
                new_id = str(uuid.uuid4())[:8]
                self.config.set_operator_id(new_id)
                print(f"🆔 ID Gerado localmente: {new_id}")

            # Nome e Descrição
            nome_default = f"Operador-{HOSTNAME}"
            nome = input(f"Nome do operador [{nome_default}]: ").strip() or nome_default
            self.config.set_operator_name(nome)
            
            descricao_default = f"Operador para {HOSTNAME}"
            input(f"Descrição (opcional) [{descricao_default}]: ").strip() # Apenas para manter UX igual, config não salva descr ainda

            # Tipo de Cadastro
            print("\n📋 Tipo de Cadastro:")
            print("   1: Monitor de Senhas (Exibe senhas chamadas na TV)")
            print("   2: Totem de Senhas (Permite chamar senhas)")
            print("   3: Ambos (Executa o Monitor e o Totem na mesma máquina)")
            
            tipo_cadastro = 'Monitor de Senhas'
            tipo_map = {'1': 'Monitor de Senhas', '2': 'Totem de Senhas', '3': 'Ambos'}
            while True:
                choice = input("Escolha o tipo [1]: ").strip() or '1'
                if choice in tipo_map:
                    tipo_cadastro = tipo_map[choice]
                    self.config.set_tipo_cadastro(tipo_cadastro)
                    break
                print("Opção inválida. Por favor, escolha 1, 2 ou 3.")

            # Credenciais
            usa_separadas = False
            if tipo_cadastro == 'Ambos':
                usa_separadas_choice = input("\nDeseja usar credenciais diferentes para Monitor e Totem? (s/N): ").strip().lower()
                if usa_separadas_choice in ['s', 'sim']:
                    usa_separadas = True
                    self.config.set_usa_credenciais_separadas(True)
                    
                    print("\n🔑 Credenciais do Monitor (TV):")
                    u_mon = input("Usuário Tasy do Monitor: ").strip()
                    p_mon = getpass.getpass("Senha Tasy do Monitor: ").strip()
                    self.config.set_credentials('tasy_monitor', u_mon, p_mon)

                    print("\n🔑 Credenciais do Totem (Chamada):")
                    u_tot = input("Usuário Tasy do Totem: ").strip()
                    p_tot = getpass.getpass("Senha Tasy do Totem: ").strip()
                    self.config.set_credentials('tasy_totem', u_tot, p_tot)

            if not usa_separadas:
                print("\n🔑 Credenciais do Tasy:")
                user = input("Usuário Tasy: ").strip()
                pwd = getpass.getpass("Senha Tasy: ").strip()
                
                if user and pwd:
                    # Correção: set_credentials recebe (section, user, pwd) apenas 3 args + self
                    self.config.set_credentials('tasy_compartilhado', user, pwd)
                else:
                    logger.error("❌ Usuário/Senha são obrigatórios.")
                    return False
            
            self.config.save_config()
            logger.info("✅ Configuração local salva com sucesso.")
            return True

        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Registro cancelado pelo usuário")
            return False
        except Exception as e:
            logger.error(f"Erro no registro local: {e}")
            return False

    def _register_operator(self) -> bool:
        try:
            success, operator_id, data = self.server_api.interactive_registration()
            if not success:
                return False
            self.config.update_from_dict(data)
            return True
        except Exception as e:
            logger.error(f"Falha no registro com servidor: {e}")
            return False

    def _handle_command(self, command: str, data: dict):
        target_str = data.get('target', 'ambos')
        logger.info(f"📩 Comando '{command}' recebido do servidor para alvo: '{target_str}'.")
        
        if self.websocket:
            self.websocket.send_command_ack(command, target_str)
        
        threading.Thread(
            target=self._execute_command_async,
            args=(command, target_str),
            name=f"CmdExec-{command}-{target_str}",
            daemon=True
        ).start()

    def _execute_command_async(self, command: str, target: str):
        try:
            success = True
            msg = "Comando executado com sucesso"

            if command == "iniciar":
                self._start_automation(target=target)
            elif command == "parar":
                self._stop_automation(target=target)
            elif command == "reiniciar":
                self._restart_automation(target=target, motivo='Comando do servidor')
            else:
                success = False
                msg = f"Comando desconhecido: {command}"
                logger.warning(f"⚠️ {msg}")

            if self.websocket:
                self.websocket.send_command_result(command, target, success, msg)
                self._send_status_update()

        except Exception as e:
            logger.error(f"❌ Erro ao executar comando '{command}': {e}", exc_info=True)
            if self.websocket:
                self.websocket.send_command_result(command, target, False, str(e))

    def _handle_config_update(self, data: dict):
        with self.automation_lock:
            log_data = data.copy()
            for key in log_data:
                if 'password' in key:
                    log_data[key] = '********'
            logger.info(f"⚙️ Configuração remota recebida do servidor: {log_data}")

            self.config.update_from_dict(data)
            logger.info("💾 Configurações locais atualizadas.")
            if data.get('reiniciar_automacao') is True:
                self._restart_automation(target='ambos', motivo='Configuração alterada')

    def _handle_reset_command(self):
        """Executa o reset total da aplicação solicitado pelo servidor"""
        logger.critical("🚨 EXECUÇÃO DO PROTOCOLO DE RESET 🚨")
        
        # 1. Parar tudo
        self.running = False
        self._stop_automation(target='ambos')
        if self.websocket:
            self.websocket.disconnect()
            
        # 2. Limpar dados
        if reset_application_data(self.config.config_file):
            logger.info("✅ Configuração removida. Encerrando aplicação...")
        else:
            logger.error("❌ Falha ao remover configuração.")
            
        # 3. Encerrar processo
        logger.info("👋 Bye bye.")
        os._exit(0)

    def _handle_automation_status_change(self, automation_type: str, new_status: str):
        if hasattr(self, 'ui_manager') and self.ui_manager:
            with self.automation_lock:
                status_geral = {t: i.status for t, i in self.automations.items()}
                if automation_type not in status_geral:
                    status_geral[automation_type] = new_status
                status_geral['connected'] = self.status == STATUS_CONNECTED

            self.ui_manager.update_data(status=status_geral)

    def _on_websocket_connected(self):
        self.status = STATUS_CONNECTED
        logger.info("🌐 WebSocket Conectado! Sincronizando status e dados de cadastro...")
        
        # 1. Sincronizar cadastro (Enviar dados offline para o server salvar no DB)
        try:
            extra_data = {
                'tipo_cadastro': self.config.get_tipo_cadastro(),
                'usa_credenciais_separadas': self.config.get_usa_credenciais_separadas(),
                'username_monitor': self.config.get_credentials('tasy_monitor')[0],
                'username_totem': self.config.get_credentials('tasy_totem')[0],
                'username': self.config.get_credentials('tasy_compartilhado')[0],
                # Metadados só de monitoramento — versão do agente e voz/idioma
                # em uso. Vão no registro (uma vez por conexão) e não influenciam
                # em nada o fluxo de automação/login/TTS.
                'versao': VERSION,
                'voz': DEFAULT_VOICE_NAME,
                'idioma': DEFAULT_VOICE_LANG,
            }
            self.websocket.register_operator(extra_data=extra_data)
        except Exception as e:
            logger.error(f"Erro ao sincronizar cadastro via WebSocket: {e}")

        # 2. Enviar status atual
        self._send_status_update()

    def _on_websocket_disconnected(self):
        self.status = STATUS_DISCONNECTED

    def _get_targets(self, target: str) -> list:
        tipo_cadastro = self.config.get_tipo_cadastro()
        if tipo_cadastro == CADASTRO_AMBOS:
            if target == TARGET_AMBOS: return [TARGET_MONITOR, TARGET_TOTEM]
            if target in [TARGET_MONITOR, TARGET_TOTEM]: return [target]
        elif tipo_cadastro == CADASTRO_MONITOR:
            return [TARGET_MONITOR]
        elif tipo_cadastro == CADASTRO_TOTEM:
            return [TARGET_TOTEM]
        return []

    def _start_automation(self, target: str = TARGET_AMBOS):
        with self.automation_lock:
            targets = self._get_targets(target)
            
            if not self.config.has_any_credentials():
                logger.error("❌ Credenciais Tasy não configuradas. Cadastre localmente ou via servidor."); return

            try:
                original_monitors = get_monitors_info()
                # Mesma regra de sempre (maior = painel, menor = totem), porém
                # medida pelo tamanho FÍSICO das telas. Em pixels os painéis
                # empatavam (1920x1080 nas duas) e a atribuição virava sorteio.
                monitor_menor_idx, monitor_maior_idx = resolve_monitor_indices(
                    original_monitors,
                    self.config.get_monitor_preference('totem'),
                    self.config.get_monitor_preference('painel'),
                )
                logger.info(f"Monitores detectados: {len(original_monitors)}.")
            except Exception as e:
                logger.error(f"Falha ao determinar monitores, usando padrão. Erro: {e}")
                monitor_maior_idx = 0
                monitor_menor_idx = 1 if len(get_monitors_info()) > 1 else 0

            use_separate = self.config.get_usa_credenciais_separadas()
            shared_creds = self.config.get_credentials('tasy_compartilhado')
            monitor_creds = self.config.get_credentials('tasy_monitor') if use_separate else shared_creds
            totem_creds = self.config.get_credentials('tasy_totem') if use_separate else shared_creds

            automation_params = {
                TARGET_MONITOR: {
                    'type': CADASTRO_MONITOR,
                    'port': AUTOMATION_PORT_MONITOR,
                    'index': monitor_maior_idx,
                    'credentials': monitor_creds
                },
                TARGET_TOTEM: {
                    'type': CADASTRO_TOTEM,
                    'port': AUTOMATION_PORT_TOTEM,
                    'index': monitor_menor_idx,
                    'credentials': totem_creds
                }
            }

            for t in targets:
                if self.automation_threads.get(t) and self.automation_threads[t].is_alive():
                    logger.warning(f"⚠️ Automação para '{t}' já está em execução.")
                    continue
                
                params = automation_params[t]
                creds = params['credentials']

                if not all(creds[:2]):
                    logger.error(f"❌ Credenciais (usuário/senha) para '{t}' estão incompletas. Automação não iniciada.")
                    continue

                logger.info(f"🚀 Iniciando thread de automação para '{params['type']}'...")
                
                instance = TasyAutomation(
                    usuario=creds[0], senha=creds[1], codigo_maquina=creds[2],
                    automation_type=params['type'],
                    tasy_url=self.config.get_tasy_url(),
                    debug_port=params['port'], 
                    monitor_index=params['index'],
                    websocket_client=self.websocket,
                    on_status_change=self._handle_automation_status_change,
                    config=self.config
                )
                self.automations[t] = instance
                thread = threading.Thread(target=instance.run, name=f"AutomacaoThread-{t}", daemon=True)
                self.automation_threads[t] = thread
                thread.start()

                if len(targets) > 1 and t == TARGET_MONITOR:
                    logger.info("⏸️ Pausando por 10s antes de iniciar a próxima automação...")
                    time.sleep(10)

    def _stop_automation(self, target: str = 'ambos'):
        with self.automation_lock:
            targets_to_stop = self._get_targets(target)
            logger.info(f"⏹️ Recebido pedido para parar automação para alvo(s): {targets_to_stop}...")

            for t in targets_to_stop:
                thread = self.automation_threads.get(t)
                instance = self.automations.get(t)

                if thread and thread.is_alive() and instance:
                    logger.info(f"   - Parando instância '{t}'...")
                    instance.crashed = False
                    instance.stop()
                    thread.join(timeout=15)

                    if thread.is_alive():
                        logger.warning(f"   - ⚠️ A thread de automação '{t}' não respondeu ao comando de parada a tempo.")
                else:
                    logger.warning(f"   - Tentativa de parar uma automação não existente ou já parada: '{t}'")

                self.automation_threads.pop(t, None)
                self.automations.pop(t, None)
                logger.info(f"   - Instância '{t}' removida do controle.")

    def _restart_automation(self, target: str = 'ambos', motivo: str = None):
        """Reinicia a automação, absorvendo pedidos concorrentes para o mesmo alvo.

        Por que a absorção existe: antes, cada pedido de reinício apenas aguardava
        o automation_lock e então executava stop+start. Pedidos em rajada — servidor
        reenviando o comando, duplo clique no painel, ou o monitor de saúde
        disparando junto com o agendador diário — enfileiravam, e o pedido seguinte
        derrubava a instância que o anterior tinha acabado de subir. O resultado era
        InvalidSessionIdException, ciclo de reinício, e a fala agendada da automação
        cortada antes de sair.

        A marcação é liberada em `finally`: mesmo que stop/start levantem exceção,
        o alvo nunca fica permanentemente bloqueado para novos reinícios.
        """
        targets_to_restart = self._get_targets(target)

        with self._restart_lock:
            em_andamento = [t for t in targets_to_restart if t in self._restarting]
            if em_andamento:
                logger.warning(
                    f"🔄 Reinício já em andamento para {em_andamento}. "
                    f"Pedido para '{target}' absorvido pelo reinício em curso."
                )
                return
            self._restarting.update(targets_to_restart)

        # Cronometragem só para o histórico de monitoramento — não altera em
        # nada a lógica de reinício. Envolvido em try/except no reporte.
        _inicio = datetime.now()
        _sucesso = False
        try:
            with self.automation_lock:
                logger.info(f"🔄 Reiniciando automação para alvo(s): {targets_to_restart}...")
                self._stop_automation(target=target)
                time.sleep(5)
                self._start_automation(target=target)
            # Sucesso REAL = a automação chegou ao estado OPERACIONAL (Tasy
            # carregado e monitor "ativado"), não apenas a thread viva. A espera
            # fica FORA do automation_lock para não travar comandos concorrentes
            # (o alvo já está protegido de reinícios simultâneos por _restarting).
            _sucesso = self._aguardar_operacional(targets_to_restart, RTO_TIMEOUT_S)
            if _sucesso:
                logger.info(f"✅ Recuperação concluída: {targets_to_restart} operacional(is).")
            else:
                logger.warning(f"⚠️ Recuperação de {targets_to_restart} não ficou operacional "
                               f"em {RTO_TIMEOUT_S}s (ou o Tasy ainda está indisponível).")
        finally:
            with self._restart_lock:
                self._restarting.difference_update(targets_to_restart)
            # Reporte do evento — isolado; qualquer falha aqui é engolida e
            # jamais afeta o reinício que acabou de ocorrer.
            try:
                self.event_reporter.registrar_reinicio(
                    motivo=motivo or 'Reinicialização',
                    alvo=target,
                    inicio=_inicio,
                    fim=datetime.now(),
                    sucesso=_sucesso,
                )
            except Exception:
                pass

    def _instancia_operacional(self, t) -> bool:
        """True se o alvo está REALMENTE operacional: thread viva, não crashou e
        a automação chegou ao estado 'ativado' (Tasy carregado, monitor ativo)."""
        inst = self.automations.get(t)
        th = self.automation_threads.get(t)
        if not inst or not th or not th.is_alive():
            return False
        if getattr(inst, 'crashed', False):
            return False
        return 'ativado' in str(getattr(inst, 'status', '')).lower()

    def _alvo_falhou(self, t) -> bool:
        """Falha definitiva do alvo: a thread morreu ou a automação crashou.
        Permite concluir o resultado sem esperar o timeout inteiro."""
        inst = self.automations.get(t)
        th = self.automation_threads.get(t)
        if th is None or not th.is_alive():
            return True
        return bool(getattr(inst, 'crashed', False))

    def _aguardar_operacional(self, targets, timeout_s) -> bool:
        """Espera todos os alvos ficarem operacionais, ou concluir falha/timeout.

        Isto define o RTO real do reinício: o painel só conta como recuperado
        quando o Tasy está de pé e o monitor ativado. Se o Tasy continuar
        indisponível, a automação crasha durante o fluxo e isto retorna False —
        agora o resultado 'falha' reflete a realidade (painel NÃO operacional),
        em vez de marcar falha com o painel funcionando.
        """
        limite = time.monotonic() + timeout_s
        while time.monotonic() < limite:
            if all(self._instancia_operacional(t) for t in targets):
                return True
            # Falha definitiva de algum alvo encerra a espera mais cedo.
            if any(self._alvo_falhou(t) for t in targets):
                return False
            time.sleep(RTO_POLL_S)
        return False

    def _send_status_update(self):
        status_geral = {t: i.status for t, i in self.automations.items()}
        running_instances = [t for t, th in self.automation_threads.items() if th.is_alive()]

        if hasattr(self, 'ui_manager') and self.ui_manager:
            ui_status = status_geral.copy()
            ui_status['connected'] = self.status == STATUS_CONNECTED
            
            server_url = self.config.get_server_url()
            try:
                server_ip = server_url.split("//")[-1].split(":")[0]
            except:
                server_ip = server_url

            use_separate = self.config.get_usa_credenciais_separadas()
            if use_separate:
                u_mon, _, _ = self.config.get_credentials('tasy_monitor')
                u_tot, _, _ = self.config.get_credentials('tasy_totem')
                tasy_user = f"Mon:{u_mon} | Tot:{u_tot}"
            else:
                u_comp, _, _ = self.config.get_credentials('tasy_compartilhado')
                tasy_user = u_comp

            self.ui_manager.update_data(
                status=ui_status,
                client_details={
                    "name": self.config.get_operator_name(),
                    "id": self.config.get_operator_id(),
                    "profile": self.config.get_tipo_cadastro(),
                    "description": "Operador Local",
                    "server_ip": server_ip,
                    "tasy_user": tasy_user,
                    "tasy_url": self.config.get_tasy_url()
                },
                sys_info=get_system_info()
            )

        if self.websocket and self.websocket.is_connected():
            status_data = {
                'status': status_geral if status_geral else self.status,
                'automation_running': bool(running_instances),
                'running_instances': running_instances,
                'system_info': get_system_info(),
            }
            self.websocket.send_status_update(status_data)

    def _status_update_loop(self):
        while self.running:
            self._send_status_update()
            time.sleep(STATUS_UPDATE_INTERVAL)

    # ─── Health Metrics ──────────────────────────────────────────────────────

    def _collect_health_metrics(self) -> dict:
        """Coleta CPU, RAM, disco e temperatura do equipamento local."""
        try:
            cpu_pct = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            temp = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for fonte in ('coretemp', 'k10temp', 'cpu_thermal', 'acpitz'):
                        if fonte in temps and temps[fonte]:
                            temp = round(temps[fonte][0].current, 1)
                            break
                    if temp is None:
                        primeira = next(iter(temps.values()))
                        if primeira:
                            temp = round(primeira[0].current, 1)
            except Exception:
                pass

            return {
                'cpu_pct':   round(cpu_pct, 1),
                'ram_pct':   round(ram.percent, 1),
                'disco_pct': round(disk.percent, 1),
                'temperatura': temp,
            }
        except Exception as e:
            logger.warning(f"Erro ao coletar métricas de saúde: {e}")
            return {}

    def _health_metrics_loop(self):
        """Envia métricas de saúde ao servidor a cada 30 segundos."""
        # Aguarda 15s no boot para o WebSocket estar conectado
        time.sleep(15)
        while self.running:
            try:
                metrics = self._collect_health_metrics()
                if metrics and self.websocket and self.websocket.is_connected():
                    metrics['id'] = self.config.get_operator_id()
                    self.websocket.send_message('saude_operador', metrics)
                    logger.debug(
                        f"Saúde enviada — CPU={metrics.get('cpu_pct')}% "
                        f"RAM={metrics.get('ram_pct')}% "
                        f"Disco={metrics.get('disco_pct')}%"
                    )
                # Aproveita o mesmo tick para escoar eventos (erros) bufferizados.
                # Isolado: falha aqui não afeta o envio de saúde.
                try:
                    self.event_reporter.flush()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Erro no loop de métricas de saúde: {e}")
            time.sleep(30)

    def _run_daily_task(self):
        logger.info("⏰ [AGENDADOR] Executando tarefa diária: Reiniciar todas as automações.")
        self._restart_automation(target='ambos', motivo='Agendamento diário')

    def _run_scheduler(self):
        logger.info("📅 [AGENDADOR] Serviço de agendamento de tarefas iniciado.")
        schedule.every().day.at("06:50").do(self._run_daily_task)
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def _monitor_automations(self):
        while self.running:
            time.sleep(AUTOMATION_MONITOR_INTERVAL)
            with self.automation_lock:
                crashed_targets = []
                for target, thread in self.automation_threads.items():
                    if not thread.is_alive():
                        instance = self.automations.get(target)
                        if instance and instance.crashed:
                            crashed_targets.append(target)
                
                for target in crashed_targets:
                    logger.warning(f"🩺 [MONITOR DE SAÚDE] Detectado que a automação '{target}' parou inesperadamente.")
                    self.automation_threads.pop(target, None)
                    self.automations.pop(target, None)
                    delay = 10
                    logger.info(f"   - Agendando reinício completo para '{target}' em {delay} segundos...")
                    threading.Timer(delay, self._restart_automation, args=[target, 'Recuperação automática']).start()

    def run(self) -> int:
        try:
            logger.info("🚀 Iniciando Cliente Operador (Modo Offline-First)")
            
            if not self._ensure_operator_registered(): 
                logger.critical("❌ Falha fatal: Não foi possível configurar o operador (nem online nem offline).")
                return 1

            operator_id = self.config.get_operator_id()
            operator_name = self.config.get_operator_name()
            logger.info(f"ℹ️ Cliente Identificado: {operator_name} | ID: {operator_id}")
            
            self.running = True
            threading.Thread(target=self._run_scheduler, daemon=True, name="SchedulerThread").start()
            threading.Thread(target=self._status_update_loop, daemon=True, name="StatusThread").start()
            threading.Thread(target=self._monitor_automations, daemon=True, name="MonitorThread").start()
            threading.Thread(target=self._health_metrics_loop, daemon=True, name="HealthThread").start()
            
            threading.Thread(
                target=self.websocket.connect, 
                args=(operator_id, operator_name),
                daemon=True,
                name="WSConnectionThread"
            ).start()

            if self.config.get_system_config().get('auto_start', False):
                logger.info("▶️ Auto-start da automação ativado.")
                self._start_automation(target='ambos')

            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("🛑 Interrupção de teclado detectada.")
        finally:
            self._cleanup()
        return 0

    def _cleanup(self):
        logger.info("\n🧹 Encerrando... Limpando todos os recursos.")
        self.running = False
        self._stop_automation(target='ambos')
        if self.websocket: self.websocket.disconnect()
        logger.info("Forçando o encerramento de todos os processos do Edge para garantir a limpeza.")
        kill_edge_processes()
        logger.info("👋 Cliente encerrado.")
