import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

/**
 * Porte da CENTRAL DE NOTIFICAÇÕES de dashboard.js (o sino do cabeçalho).
 *
 * Comportamento preservado integralmente:
 *  - chave 'hsv_notif_v1' no localStorage, máximo de 20 itens
 *  - notificações novas entram no topo (unshift)
 *  - só emite em TRANSIÇÃO de estado; o primeiro carregamento apenas registra
 *    o estado base sem notificar (_notifPrev.loaded)
 *  - transições cobertas: online↔offline e mudança de nível de saúde
 *  - nível 'Normal' não gera notificação
 */

const NotificacoesContext = createContext(null)
export const useNotificacoes = () => useContext(NotificacoesContext)

const NOTIF_KEY = 'hsv_notif_v1'
const NOTIF_MAX = 20

function carregar() {
  try {
    return JSON.parse(localStorage.getItem(NOTIF_KEY) || '[]')
  } catch {
    return []
  }
}
function salvar(list) {
  try {
    localStorage.setItem(NOTIF_KEY, JSON.stringify(list.slice(0, NOTIF_MAX)))
  } catch {
    /* ignora, igual ao original */
  }
}

export function NotificacoesProvider({ children }) {
  const [lista, setLista] = useState(() => carregar())

  // Estado anterior para detectar transições — porte de _notifPrev
  const anterior = useRef({ online: {}, nivel: {}, loaded: false })

  const persistir = useCallback((nova) => {
    salvar(nova)
    setLista(nova.slice(0, NOTIF_MAX))
  }, [])

  const adicionar = useCallback(
    (type, title, message, operadorId) => {
      const atual = carregar()
      atual.unshift({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        type, title, message,
        timestamp: new Date().toISOString(),
        read: false,
        operadorId: operadorId || null,
      })
      persistir(atual)
    },
    [persistir]
  )

  const marcarLida = useCallback(
    (id) => persistir(carregar().map((n) => (n.id === id ? { ...n, read: true } : n))),
    [persistir]
  )
  const marcarTodasLidas = useCallback(
    () => persistir(carregar().map((n) => ({ ...n, read: true }))),
    [persistir]
  )
  const limparTodas = useCallback(() => persistir([]), [persistir])

  /** Registra o estado base sem emitir — porte de _notifInitBaseState(). */
  const inicializarEstadoBase = useCallback((operadores) => {
    if (anterior.current.loaded) return
    ;(operadores || []).forEach((op) => {
      anterior.current.online[op.id] = !!op.online
      anterior.current.nivel[op.id] = op.nivel_saude || 'Normal'
    })
    anterior.current.loaded = true
  }, [])

  /** Porte de _notifCheckOnlineChange(). */
  const checarMudancaOnline = useCallback(
    (operadorId, isOnline, nome) => {
      if (!anterior.current.loaded) return
      const prev = anterior.current.online[operadorId]
      anterior.current.online[operadorId] = isOnline
      if (prev === undefined || prev === isOnline) return

      const hora = new Date().toLocaleTimeString('pt-BR')
      if (!isOnline) {
        adicionar('offline', `${nome} ficou offline`, `Comunicação perdida às ${hora}`, operadorId)
      } else {
        adicionar('online', `${nome} voltou online`, `Conexão restabelecida às ${hora}`, operadorId)
      }
    },
    [adicionar]
  )

  /** Porte de _notifCheckHealthChange(). */
  const checarMudancaSaude = useCallback(
    (operadorId, nivel, motivos, nome) => {
      if (!anterior.current.loaded) return
      const prev = anterior.current.nivel[operadorId]
      anterior.current.nivel[operadorId] = nivel
      if (prev === undefined || prev === nivel) return
      if (nivel === 'Normal') return

      const type = nivel === 'Crítico' ? 'health_critico' : 'health_atencao'
      const msg = motivos && motivos[0] ? motivos[0] : `Nível ${nivel} detectado.`
      adicionar(type, `${nome} requer atenção`, msg, operadorId)
    },
    [adicionar]
  )

  // Mantém a lista em sincronia se outra aba alterar o localStorage
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === NOTIF_KEY) setLista(carregar())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const naoLidas = lista.filter((n) => !n.read).length

  return (
    <NotificacoesContext.Provider
      value={{
        lista, naoLidas,
        marcarLida, marcarTodasLidas, limparTodas,
        inicializarEstadoBase, checarMudancaOnline, checarMudancaSaude,
      }}
    >
      {children}
    </NotificacoesContext.Provider>
  )
}
