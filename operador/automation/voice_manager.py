import logging
from typing import Optional

logger = logging.getLogger("TasyOperador.VoiceManager")

class VoiceManager:
    """Gerenciador de síntese de voz simplificado usando a voz padrão do browser."""
    
    def __init__(self, driver=None):
        self.driver = driver
        
    def set_driver(self, driver):
        """Define o driver do navegador."""
        self.driver = driver

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
