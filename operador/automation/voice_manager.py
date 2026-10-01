import logging
from typing import Optional

logger = logging.getLogger("TasyOperador.VoiceManager")

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
# Só age quando a voz é multilíngue ou não foi definida; caso contrário não toca
# em nada — se o Tasy passar a escolher direito, este script fica inerte.
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

    var original = synth.speak.bind(synth);
    synth.speak = function (u) {
      try {
        if (u) {
          if (!u.lang) u.lang = 'pt-BR';
          if (!u.voice || MULTILINGUE.test(u.voice.name || '')) {
            var boa = escolherVoz();
            if (boa) u.voice = boa;
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


class VoiceManager:
    """Gerenciador de síntese de voz simplificado usando a voz padrão do browser."""
    
    def __init__(self, driver=None):
        self.driver = driver
        
    def set_driver(self, driver):
        """Define o driver do navegador e instala a correção de voz das chamadas."""
        self.driver = driver
        self.garantir_voz_ptbr()

    def garantir_voz_ptbr(self) -> bool:
        """Instala, uma vez por documento, a correção de voz das chamadas do Tasy.

        Idempotente e barata: se já estiver instalada, o script devolve
        'ja-instalado' e não faz nada. Chamada em set_driver() e no início de
        speak(), o que cobre o ciclo normal da automação.

        Se o documento for recarregado de fato, o gancho se perde — mas nesse
        cenário a automação também perde as referências dos elementos,
        `_is_healthy()` falha e o restart existente recria o navegador,
        reinstalando a correção. Por isso não há reinjeção periódica aqui.

        NUNCA levanta exceção: falhar em instalar não pode derrubar a automação.
        """
        if not self.driver:
            return False
        try:
            resultado = self.driver.execute_script(_CORRECAO_PTBR_JS)
        except Exception as e:
            logger.warning(f"🔊 Correção de voz não pôde ser instalada (não crítico): {e}")
            return False

        if resultado == 'instalado':
            logger.info("🔊 Correção de voz pt-BR instalada no painel "
                        "(troca voz multilíngue do Tasy por voz pt-BR comum).")
        elif resultado != 'ja-instalado':
            logger.warning(f"🔊 Correção de voz não instalada: {resultado}")
        return resultado in ('instalado', 'ja-instalado')

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
