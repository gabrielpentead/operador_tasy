import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../services/auth'

/**
 * Estado da sessão.
 *
 * A verdade sobre quem está logado é sempre do servidor: ao carregar, o app
 * pergunta em /api/auth/me. Nada é deduzido de dado guardado no navegador, o
 * que impede que alguém se "promova" a administrador mexendo no localStorage.
 */
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const verificar = useCallback(async () => {
    try {
      const r = await authApi.me()
      setUsuario(r.autenticado ? r.usuario : null)
    } catch {
      setUsuario(null)
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => { verificar() }, [verificar])

  const entrar = useCallback(async (login, senha) => {
    const r = await authApi.login(login, senha)
    if (r.ok && r.success) {
      setUsuario(r.usuario)
      return { ok: true }
    }
    return { ok: false, erro: r.error || 'Não foi possível entrar' }
  }, [])

  const sair = useCallback(async () => {
    try { await authApi.logout() } finally { setUsuario(null) }
  }, [])

  const valor = {
    usuario,
    carregando,
    autenticado: usuario !== null,
    isAdmin: usuario?.role === 'admin',
    entrar,
    sair,
    verificar,
  }

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>')
  return ctx
}
