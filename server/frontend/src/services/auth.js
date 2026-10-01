/**
 * Chamadas de autenticação.
 *
 * Todas usam credentials:'include' para o cookie de sessão ir junto. O token
 * NÃO é lido nem guardado pelo JavaScript: o cookie é HttpOnly, então nada
 * sensível fica acessível no navegador (nem em localStorage, nem em memória).
 */
const base = '/api/auth'

async function req(caminho, opcoes = {}) {
  const r = await fetch(base + caminho, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opcoes,
  })
  let dados = {}
  try { dados = await r.json() } catch { /* resposta sem corpo */ }
  return { ok: r.ok, status: r.status, ...dados }
}

export const authApi = {
  me:      ()            => req('/me'),
  login:   (login, senha) => req('/login',  { method: 'POST', body: JSON.stringify({ login, senha }) }),
  logout:  ()            => req('/logout', { method: 'POST' }),
  trocarPropriaSenha: (senha_atual, senha_nova) =>
    req('/senha', { method: 'POST', body: JSON.stringify({ senha_atual, senha_nova }) }),

  esqueciSenha: (email) => req('/esqueci-senha', { method: 'POST', body: JSON.stringify({ email }) }),

  // O token viaja no corpo, nunca na query da chamada: assim não entra no log
  // de acesso do servidor nem em cache de proxy.
  validarToken: (token) => req('/validar-token', { method: 'POST', body: JSON.stringify({ token }) }),
  redefinirComToken: (token, senha) =>
    req('/redefinir', { method: 'POST', body: JSON.stringify({ token, senha }) }),

  listarUsuarios: ()      => req('/usuarios'),
  criarUsuario:   (dados) => req('/usuarios', { method: 'POST', body: JSON.stringify(dados) }),
  editarUsuario:  (id, dados) => req(`/usuarios/${id}`, { method: 'PUT', body: JSON.stringify(dados) }),
  excluirUsuario: (id)    => req(`/usuarios/${id}`, { method: 'DELETE' }),
  redefinirSenha: (id)    => req(`/usuarios/${id}/redefinir-senha`, { method: 'POST' }),
}
