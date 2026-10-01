/**
 * Constantes do frontend.
 *
 * A antiga SENHA_ADMIN ('n3t2i1') foi REMOVIDA. Ela era comparada no navegador
 * e viajava no bundle, legível por qualquer visitante da página. O painel agora
 * exige login real, então a verificação de identidade acontece no servidor e
 * uma segunda senha no cliente não acrescentava proteção alguma.
 */

/** Porte do objeto CONFIG de common.js. */
export const CONFIG = {
  atualizacaoAutomatica: true,
  intervaloAtualizacao: 30000,
  timeoutNotificacao: 5000,
}

/**
 * Limites de usuário e senha. Precisam espelhar SENHA_MAX/LOGIN_MAX do auth.py:
 * o front evita o envio inválido, mas quem garante é o servidor.
 */
export const LOGIN_MAX = 15
export const SENHA_MAX = 15
export const SENHA_MIN = 6
