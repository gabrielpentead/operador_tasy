import logging
import time
from typing import Optional

logger = logging.getLogger("TasyOperador.VoiceManager")

# Intervalo mínimo entre duas verificações periódicas da voz (verificar_voz), chamada
# pelo laço de saúde da automação a cada poucos segundos.
VERIFICACAO_VOZ_S = 60

# Erros de fala que NÃO indicam defeito: o próprio Tasy cancela/interrompe chamadas.
_ERROS_DE_FALA_IGNORADOS = ('interrupted', 'canceled')

# Espelham exatamente os literais usados dentro de VoiceManager.speak(): o nome da
# voz e o lang do utterance. Existem só para o operador PODER REPORTAR ao servidor
# qual voz/idioma está em uso (monitoramento), sem que nada leia estas constantes
# no caminho da fala. Se algum dia o literal em speak() mudar, atualizar aqui junto.
DEFAULT_VOICE_NAME = "Microsoft Francisca Online (Natural) - Portuguese (Brazil)"
DEFAULT_VOICE_LANG = "pt-BR"


# Script injetado UMA vez no documento do painel. Corrige o utterance das chamadas
# de senha do TASY (AtePacSEVoice.speak), que não é nosso código.
#
# POR QUE EXISTE: a partir do Edge 153 o catálogo da Microsoft passou a expor a
# "Microsoft Thalita multilíngue Online (Natural) - Portuguese (Brazil)". O Tasy
# escolhe essa voz e NÃO define `lang` no utterance. Sendo multilíngue, ela detecta
# o idioma pelo próprio texto e erra: nomes de paciente saem em inglês/espanhol.
# Medido em campo (monitor_falas, 14/09/2026): 110 chamadas com voz=Thalita e
# lang=(vazio); as 3 falas do operador, com voz e lang explícitos, saíram corretas.
#
# POR QUE TROCA A VOZ em vez de só preencher o lang: testado no painel afetado —
# com a Thalita, definir lang='pt-BR' NÃO corrige (continua em inglês). Só a troca
# por uma voz não-multilíngue resolve. Não é suposição, é medição.
#
# SEGURANÇA: o ajuste roda dentro de try/catch e a chamada original é SEMPRE
# repassada. Uma falha aqui nunca pode calar uma chamada de paciente.
#
# 1.5.10 (15/10/2026, Edge 155): passa a IMPOR a Francisca e o pt-BR em TODA fala,
# não só quando a voz pedida é multilíngue. Requisito do NTI: as chamadas saem
# exclusivamente na voz da Francisca e nunca em outro idioma. Se a Francisca ainda
# não estiver no catálogo (só nos primeiros instantes após abrir o Edge), usa outra
# voz pt-BR não multilíngue — nunca a voz que o Tasy pediu, se ela for de outro idioma.
# Registra em __vozDiag a voz que o Tasy PEDIU e a que de fato FOI usada.
_CORRECAO_PTBR_JS = r"""
(function () {
  try {
    var synth = window.speechSynthesis;
    if (!synth || typeof synth.speak !== 'function') return 'sem-speechSynthesis';
    if (window.__correcaoPtBrInstalada === true) return 'ja-instalado';

    var MULTILINGUE = /multiling|multilíng/i;
    var PREFERIDAS = [
      'Microsoft Francisca Online (Natural) - Portuguese (Brazil)',
      'Microsoft Antônio Online (Natural) - Portuguese (Brazil)',
      'Microsoft Maria - Portuguese (Brazil)',
      'Microsoft Daniel - Portuguese (Brazil)'
    ];

    function escolherVoz() {
      var vs = synth.getVoices() || [];
      for (var i = 0; i < PREFERIDAS.length; i++) {
        for (var j = 0; j < vs.length; j++) {
          if (vs[j].name === PREFERIDAS[i]) return vs[j];
        }
      }
      // Nenhuma das preferidas: qualquer pt-BR que nao seja multilingue.
      for (var k = 0; k < vs.length; k++) {
        if ((vs[k].lang || '').toLowerCase().indexOf('pt-br') === 0
            && !MULTILINGUE.test(vs[k].name || '')) return vs[k];
      }
      return null;
    }

    // Contadores PASSIVOS de cada fala (lidos por VoiceManager.verificar_voz): quantas
    // foram pedidas, quantas começaram e quais erros o navegador devolveu. Só escutam
    // com addEventListener — nunca substituem onstart/onend/onerror do Tasy.
    var diag = window.__vozDiag = { falas: 0, iniciadas: 0, erros: {}, pedidas: {}, usadas: {}, langs: {} };
    function contar(mapa, chave) { mapa[chave] = (mapa[chave] || 0) + 1; }

    var original = synth.speak.bind(synth);
    synth.speak = function (u) {
      try {
        if (u) {
          var pedida = u.voice ? u.voice.name : '(nenhuma)';
          var boa = escolherVoz();
          if (boa) {
            u.voice = boa;
          } else if (u.voice && (MULTILINGUE.test(u.voice.name || '')
                     || (u.voice.lang || '').toLowerCase().indexOf('pt-br') !== 0)) {
            u.voice = null;   // sem voz pt-BR no catálogo: nunca deixar a de outro idioma
          }
          u.lang = 'pt-BR';
          diag.falas++;
          contar(diag.pedidas, pedida);
          contar(diag.usadas, u.voice ? u.voice.name : '(padrão do navegador)');
          contar(diag.langs, u.lang);
          if (!u.__vozDiag) {
            u.__vozDiag = true;
            u.addEventListener('start', function () { diag.iniciadas++; });
            u.addEventListener('error', function (ev) {
              var k = (ev && ev.error) || 'desconhecido';
              diag.erros[k] = (diag.erros[k] || 0) + 1;
            });
          }
        }
      } catch (e) { /* jamais impedir a fala */ }
      return original(u);
    };

    window.__correcaoPtBrInstalada = true;
    return 'instalado';
  } catch (e) {
    return 'erro: ' + (e && e.message ? e.message : String(e));
  }
})();
"""


# Sonda SILENCIOSA: a página tem permissão para emitir som sem interação do usuário?
#
# POR QUE EXISTE (incidente de 15/10/2026): o Edge 155 passou a recusar
# `speechSynthesis.speak()` com o erro `not-allowed` em documentos que nunca receberam
# clique ou tecla. O login da automação é feito por JavaScript (selenium_utils), que não
# conta como interação — o painel ficava COMPLETAMENTE MUDO. Com o Edge 153 falava.
#
# A sonda cria um AudioContext sem nenhum nó (não toca nada, não entra na fila de fala
# do Tasy) e lê o estado: 'running' = som liberado; 'suspended' = bloqueado. Medido no
# Edge 155, nos três cenários, sempre igual ao resultado de uma fala real:
#   sem nada                    -> suspended -> Francisca: not-allowed
#   --autoplay-policy (abertura) -> running   -> Francisca falou
#   gesto via CDP               -> running   -> Francisca falou
_SONDA_FALA_JS = r"""
return (function () {
  var r = { ativada: !!(navigator.userActivation && navigator.userActivation.hasBeenActive), autoplay: null };
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (AC) { var c = new AC(); r.autoplay = (c.state === 'running'); try { c.close(); } catch (e) {} }
  } catch (e) { r.erro = String(e && e.message ? e.message : e); }
  return r;
})();
"""

# Instala a correção na janela principal E em todos os frames de mesma origem (recursivo).
# `w.eval(src)` executa o script no escopo global do próprio frame, então `window`
# dentro dele é o do frame. Frames de outra origem são apenas listados.
_INSTALAR_EM_TODOS_OS_FRAMES_JS = r"""
var src = arguments[0], out = [];
function instalar(w, caminho) {
  var r;
  try { r = w.eval(src); } catch (e) { r = 'erro: ' + (e && e.message ? e.message : e); }
  out.push([caminho, r]);
  var n = 0;
  try { n = w.frames.length; } catch (e) {}
  for (var i = 0; i < n; i++) {
    try { void w.frames[i].document; instalar(w.frames[i], caminho + '/' + i); }
    catch (e) { out.push([caminho + '/' + i, 'outra-origem']); }
  }
}
instalar(window, 'principal');
return out;
"""

# Soma os contadores passivos de todos os frames de mesma origem.
_LER_DIAG_JS = r"""
var t = { falas: 0, iniciadas: 0, erros: {}, pedidas: {}, usadas: {}, langs: {}, frames: 0 };
function somar(dst, src) { for (var k in (src || {})) dst[k] = (dst[k] || 0) + src[k]; }
function visitar(w) {
  var d = null;
  try { d = w.__vozDiag; } catch (e) { return; }
  if (d) {
    t.frames++; t.falas += d.falas || 0; t.iniciadas += d.iniciadas || 0;
    somar(t.erros, d.erros); somar(t.pedidas, d.pedidas); somar(t.usadas, d.usadas); somar(t.langs, d.langs);
  }
  var n = 0;
  try { n = w.frames.length; } catch (e) {}
  for (var i = 0; i < n; i++) { try { visitar(w.frames[i]); } catch (e) {} }
}
visitar(window);
return t;
"""


class VoiceManager:
    """Gerenciador de síntese de voz simplificado usando a voz padrão do browser."""
    
    def __init__(self, driver=None):
        self.driver = driver
        self._estado_fala: Optional[str] = None
        self._ultima_verificacao = 0.0
        self._diag_anterior: dict = {}

    def set_driver(self, driver):
        """Define o driver do navegador e instala a correção de voz das chamadas."""
        self.driver = driver
        self._estado_fala = None
        self._ultima_verificacao = time.monotonic()
        self._diag_anterior = {}
        self._registrar_em_documentos_novos()
        self.garantir_voz_ptbr()

    def _registrar_em_documentos_novos(self):
        """Pede ao Edge (DevTools) que rode a correção em TODO documento e frame que
        abrir daqui em diante, ANTES dos scripts da página.

        Assim a correção já está lá quando o Tasy monta a tela de senhas — mesmo que
        ele fale de dentro de um iframe, recarregue a página ou guarde uma referência
        ao speechSynthesis logo ao carregar. A injeção direta (garantir_voz_ptbr)
        continua existindo como segunda via.
        """
        try:
            # O script só roda nos documentos novos com o domínio Page ativo. O
            # msedgedriver normalmente já o ativa; ativar de novo é inofensivo.
            self.driver.execute_cdp_cmd("Page.enable", {})
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                                        {"source": _CORRECAO_PTBR_JS})
            logger.info("🔊 Correção de voz registrada para todas as páginas e frames novos.")
        except Exception as e:
            logger.warning(f"🔊 Não foi possível registrar a correção para páginas novas "
                           f"(segue pela injeção direta): {e}")

    def garantir_voz_ptbr(self) -> bool:
        """Instala a correção de voz das chamadas do Tasy na página e em todos os
        frames de mesma origem, e garante que o Edge deixe a página falar.

        Idempotente e barata: onde já estiver instalada, o script devolve
        'ja-instalado' e não faz nada. Chamada em set_driver(), no início de
        speak() e, a cada VERIFICACAO_VOZ_S, por verificar_voz() — que também
        a reinstala se algum documento ou frame tiver sido recarregado.

        Quando instala em algum documento novo, confere se a fala está liberada
        (garantir_fala_liberada).

        NUNCA levanta exceção: falhar em instalar não pode derrubar a automação.
        """
        if not self.driver:
            return False
        try:
            resultados = self.driver.execute_script(_INSTALAR_EM_TODOS_OS_FRAMES_JS, _CORRECAO_PTBR_JS)
        except Exception as e:
            logger.warning(f"🔊 Correção de voz não pôde ser instalada (não crítico): {e}")
            return False

        novos = [f for f, r in (resultados or []) if r == 'instalado']
        problemas = [(f, r) for f, r in (resultados or []) if r not in ('instalado', 'ja-instalado')]
        if novos:
            logger.info(f"🔊 Correção de voz pt-BR instalada (impõe a Francisca e o pt-BR em toda fala) "
                        f"em: {', '.join(novos)}.")
            self.garantir_fala_liberada()
        for f, r in problemas:
            logger.warning(f"🔊 Correção de voz não instalada no frame '{f}': {r}")
        return bool(resultados) and not any(f == 'principal' and r not in ('instalado', 'ja-instalado')
                                            for f, r in resultados)

    def _sondar_fala(self) -> Optional[dict]:
        """Lê, sem emitir som, se a página pode falar (ver _SONDA_FALA_JS)."""
        try:
            r = self.driver.execute_script(_SONDA_FALA_JS)
            return r if isinstance(r, dict) else None
        except Exception as e:
            logger.debug(f"🔊 Sonda de fala falhou: {e}")
            return None

    def _registrar_estado_fala(self, estado: str, nivel: int):
        """Registra no log só quando o estado da fala MUDA (evita repetir a cada minuto)."""
        if estado != self._estado_fala:
            self._estado_fala = estado
            logger.log(nivel, f"🔊 Fala {estado}")

    def garantir_fala_liberada(self, forcar_gesto: bool = False) -> bool:
        """Garante que o Edge deixe a página do painel falar.

        Duas camadas independentes, para não depender de um único comportamento
        do navegador (o que mudou entre o Edge 153 e o 155 pode mudar de novo):
          1. PRINCIPAL — o Edge é aberto com --autoplay-policy=no-user-gesture-required
             (browser_manager.start_browser). Libera a fala sem mexer na página.
          2. RESERVA — se a sonda disser que o som continua bloqueado (ou se o
             painel registrou falas recusadas com 'not-allowed'), aplica UM gesto
             de usuário via DevTools (Runtime.evaluate com userGesture). Não clica,
             não digita e não muda nada visível; só marca o documento como ativado.

        NUNCA levanta exceção.
        """
        if not self.driver:
            return False
        estado = self._sondar_fala()
        if not forcar_gesto and estado and estado.get('autoplay') is True:
            origem = "página ativada" if estado.get('ativada') else "reprodução automática do Edge"
            self._registrar_estado_fala(f"liberada ({origem}).", logging.INFO)
            return True

        try:
            self.driver.execute_cdp_cmd("Runtime.evaluate", {"expression": "void 0", "userGesture": True})
        except Exception as e:
            logger.warning(f"🔊 Não foi possível aplicar o gesto de reserva via DevTools: {e}")

        estado = self._sondar_fala()
        if estado and estado.get('autoplay') is True:
            self._registrar_estado_fala(
                "liberada por gesto via DevTools (reserva: a reprodução automática "
                "do Edge não estava valendo).", logging.WARNING)
            return True
        self._registrar_estado_fala(
            f"BLOQUEADA pelo Edge: as chamadas vão sair sem som (sonda: {estado}).", logging.ERROR)
        return False

    def verificar_voz(self):
        """Verificação periódica e leve, chamada pelo laço de saúde da automação.

        No máximo a cada VERIFICACAO_VOZ_S:
          - reinstala a correção se o documento tiver sido recarregado;
          - lê os contadores passivos das falas e registra as que FALHARAM desde a
            última leitura (assim um painel mudo aparece no log, em vez de passar
            despercebido como no incidente de 15/10/2026);
          - se houver falas recusadas com 'not-allowed', aplica a reserva.

        Não emite som, não toca na fila de fala e NUNCA levanta exceção.
        """
        if not self.driver:
            return
        agora = time.monotonic()
        if agora - self._ultima_verificacao < VERIFICACAO_VOZ_S:
            return
        self._ultima_verificacao = agora
        try:
            self.garantir_voz_ptbr()
            diag = self.driver.execute_script(_LER_DIAG_JS)
        except Exception as e:
            logger.debug(f"🔊 Verificação periódica da voz falhou: {e}")
            return
        if not isinstance(diag, dict):
            return

        anterior = self._diag_anterior
        if diag.get('falas', 0) < anterior.get('falas', 0):
            anterior = {}   # documento novo: contadores recomeçaram do zero
        self._diag_anterior = diag

        def delta(campo):
            atual, antes = diag.get(campo) or {}, anterior.get(campo) or {}
            return {k: v - antes.get(k, 0) for k, v in atual.items() if v > antes.get(k, 0)}

        falas_novas = diag.get('falas', 0) - anterior.get('falas', 0)
        if falas_novas > 0:
            usadas = delta('usadas')
            pedidas = delta('pedidas')
            fora = {k: v for k, v in usadas.items() if k != DEFAULT_VOICE_NAME}
            resumo = (f"{falas_novas} fala(s) no último minuto | voz usada: "
                      + ", ".join(f"{k.split(' - ')[0]}={v}" for k, v in sorted(usadas.items()))
                      + " | voz pedida pelo Tasy: "
                      + ", ".join(f"{k.split(' - ')[0]}={v}" for k, v in sorted(pedidas.items())))
            if fora:
                logger.warning(f"🔊 {resumo} | ATENÇÃO: fala(s) fora da Francisca.")
            else:
                logger.info(f"🔊 {resumo}")

        novos = {k: v for k, v in delta('erros').items() if k not in _ERROS_DE_FALA_IGNORADOS}
        if novos:
            resumo = ", ".join(f"{k}={v}" for k, v in sorted(novos.items()))
            logger.warning(f"🔊 Falas que falharam no último minuto: {resumo} "
                           f"(total no painel: {diag.get('falas', 0)} pedidas, "
                           f"{diag.get('iniciadas', 0)} iniciadas).")
            if 'not-allowed' in novos:
                self.garantir_fala_liberada(forcar_gesto=True)

    def speak(self, text: str) -> bool:
        """
        Fala um texto usando a voz 'Francisca', sem interferir no TTS da página.

        IMPORTANTE — este script roda DENTRO do documento do painel do Tasy, que é
        uma SPA AngularJS: login, tela principal e Gerenciamento de Senhas ocorrem
        todos no mesmo documento, compartilhando o mesmo objeto `speechSynthesis`
        que o Tasy usa para as chamadas de senha. Por isso o script:

          - usa addEventListener('voiceschanged'), NUNCA a atribuição
            `speechSynthesis.onvoiceschanged = ...`. A atribuição substituiria o
            handler que o Tasy tenha registrado, e o Tasy deixaria de montar a
            lista de vozes. Como o painel é servido com <html lang="en">, um
            utterance sem voz resolvida cai no fallback do documento e fala em
            INGLÊS — o mesmo sintoma já observado em produção;
          - remove o próprio listener depois de usar, para não deixar nada
            pendurado no documento do painel;
          - define lang apenas no utterance que ele mesmo cria, jamais no
            documento nem em objetos do Tasy.
        """
        try:
            if not self.driver or not text.strip():
                return False

            # Reforça a correção de voz das chamadas do Tasy. Idempotente: se já
            # estiver instalada não faz nada. Fica aqui porque speak() é chamado
            # depois do login, quando a página do painel já está montada.
            self.garantir_voz_ptbr()

            clean_text = text.strip().replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${').replace('\n', ' ')
            default_voice_name = "Microsoft Francisca Online (Natural) - Portuguese (Brazil)"

            script = f"""
            return (function () {{
                const text = `{clean_text}`;
                const voiceName = `{default_voice_name}`;
                const synth = window.speechSynthesis;

                const speakWith = (voices) => {{
                    const utterance = new SpeechSynthesisUtterance(text);
                    // lang apenas do NOSSO utterance: sem isso, o <html lang="en">
                    // do painel faria este texto em português ser lido por voz inglesa.
                    utterance.lang = 'pt-BR';
                    const voiceToUse = (voices || []).find(v => v.name === voiceName);
                    if (voiceToUse) {{
                        utterance.voice = voiceToUse;
                    }}
                    synth.speak(utterance);
                    return voiceToUse !== undefined;
                }};

                const voices = synth.getVoices();
                if (voices && voices.length) {{
                    return speakWith(voices);
                }}

                // Vozes ainda não carregadas. Escuta o evento SEM tocar em
                // synth.onvoiceschanged, que pode pertencer ao Tasy.
                let done = false;
                const finish = () => {{
                    if (done) return;
                    done = true;
                    synth.removeEventListener('voiceschanged', finish);
                    speakWith(synth.getVoices());
                }};
                synth.addEventListener('voiceschanged', finish);
                // Rede de segurança: se o evento nunca disparar, fala assim mesmo
                // e garante que o listener não fique preso no documento.
                setTimeout(finish, 3000);
                return null;   // fala adiada; resultado ainda desconhecido
            }})();
            """

            voice_found = self.driver.execute_script(script)

            if voice_found is False:
                logger.warning(f"🔊 Voz '{default_voice_name}' não encontrada. Usando a voz padrão do sistema.")
            elif voice_found is None:
                logger.info("🔊 Vozes ainda não carregadas; fala adiada até o evento 'voiceschanged'.")

            logger.info(f"🔊 Falando: '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}'")
            return True
        except Exception as e:
            logger.error(f"Erro ao falar: {e}")
            return False

    def stop_speaking(self) -> bool:
        """Para a síntese de voz.

        ⚠️ NÃO CHAMAR com o painel do Tasy carregado. `speechSynthesis.cancel()`
        limpa a fila GLOBAL do documento, não apenas o que esta classe enfileirou:
        cortaria uma chamada de senha do Tasy em andamento e descartaria as que
        estivessem na fila. Atualmente este método não é chamado em nenhum ponto
        do projeto — mantenha assim.
        """
        try:
            if not self.driver:
                return False
            self.driver.execute_script("window.speechSynthesis.cancel();")
            return True
        except Exception as e:
            logger.error(f"Erro ao parar voz: {e}")
            return False
