import { createContext, useContext, useState, useCallback } from 'react'

/**
 * Preferências de acessibilidade — por NAVEGADOR (localStorage), não por conta.
 *
 * Acessibilidade é uma escolha pessoal de quem está usando aquela máquina, então
 * fica no navegador: não precisa de backend, vale já na tela de login e não
 * afeta os outros usuários. Hoje há só a tradução em Libras (VLibras); novas
 * opções entram aqui do mesmo jeito.
 */

const CHAVE_LIBRAS = 'acessibilidade.libras'
const Ctx = createContext(null)

function lerBool(chave) {
  try { return localStorage.getItem(chave) === '1' } catch { return false }
}

export function AcessibilidadeProvider({ children }) {
  const [libras, setLibrasState] = useState(() => lerBool(CHAVE_LIBRAS))

  const setLibras = useCallback((ativo) => {
    setLibrasState(ativo)
    try { localStorage.setItem(CHAVE_LIBRAS, ativo ? '1' : '0') } catch { /* modo privado: ignora */ }
  }, [])

  return <Ctx.Provider value={{ libras, setLibras }}>{children}</Ctx.Provider>
}

export function useAcessibilidade() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAcessibilidade precisa do AcessibilidadeProvider')
  return ctx
}
