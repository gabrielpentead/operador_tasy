import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'

/**
 * Porte de mostrarNotificacao() / notificações persistentes de common.js.
 *
 * Comportamento preservado:
 *  - tipos válidos: info, success, warning, danger (fallback para info)
 *  - timeout padrão de 5000 ms (CONFIG.timeoutNotificacao)
 *  - notificações "persistentes" não somem sozinhas e são gravadas em
 *    localStorage sob a chave 'notificacoesPersistentes'
 *  - ao carregar a página, persistentes com menos de 24 h são reexibidas e
 *    as mais antigas são descartadas
 *
 * O que mudou: o original usava a classe Toast do Bootstrap via JS. Aqui o
 * ciclo de vida é do React, mas a marcação e as classes CSS são as mesmas,
 * então o resultado visual é idêntico.
 */

const ToastContext = createContext(null)
export const useToast = () => useContext(ToastContext)

const TIMEOUT_PADRAO = 5000
const CHAVE_PERSISTENTES = 'notificacoesPersistentes'
const LIMITE_24H = 24 * 60 * 60 * 1000

const TIPOS_VALIDOS = ['info', 'success', 'warning', 'danger']
const ICONES = {
  info: 'bi-info-circle',
  success: 'bi-check-circle',
  warning: 'bi-exclamation-triangle',
  danger: 'bi-x-circle',
}

function lerPersistentes() {
  try {
    return JSON.parse(localStorage.getItem(CHAVE_PERSISTENTES) || '{}')
  } catch {
    return {}
  }
}
function gravarPersistentes(obj) {
  try {
    localStorage.setItem(CHAVE_PERSISTENTES, JSON.stringify(obj))
  } catch {
    /* storage indisponível — ignora, igual ao original */
  }
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const remover = useCallback((id) => {
    setToasts((atuais) => atuais.filter((t) => t.id !== id))
    if (timers.current[id]) {
      clearTimeout(timers.current[id])
      delete timers.current[id]
    }
  }, [])

  const fecharPersistente = useCallback((id) => {
    const persistentes = lerPersistentes()
    if (persistentes[id]) {
      delete persistentes[id]
      gravarPersistentes(persistentes)
    }
    remover(id)
  }, [remover])

  const mostrarNotificacao = useCallback(
    (mensagem, tipo = 'info', tempo = TIMEOUT_PADRAO, persistente = false) => {
      const tipoFinal = TIPOS_VALIDOS.includes(tipo) ? tipo : 'info'
      const tempoFinal = typeof tempo === 'number' && tempo > 0 ? tempo : TIMEOUT_PADRAO
      const id = `notificacao-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

      setToasts((atuais) => [...atuais, { id, mensagem, tipo: tipoFinal, persistente }])

      if (persistente) {
        const persistentes = lerPersistentes()
        persistentes[id] = { mensagem, tipo: tipoFinal, timestamp: Date.now() }
        gravarPersistentes(persistentes)
      } else {
        timers.current[id] = setTimeout(() => remover(id), tempoFinal)
      }
      return id
    },
    [remover]
  )

  // Reexibe persistentes válidas e limpa as antigas — porte de
  // verificarNotificacoesPersistentes() + limparNotificacoesAntigas()
  useEffect(() => {
    const persistentes = lerPersistentes()
    const agora = Date.now()
    let modificado = false
    const restaurar = []

    Object.keys(persistentes).forEach((id) => {
      const n = persistentes[id]
      if (agora - n.timestamp > LIMITE_24H) {
        delete persistentes[id]
        modificado = true
      } else {
        restaurar.push({ id, mensagem: n.mensagem, tipo: n.tipo, persistente: true })
      }
    })

    if (modificado) gravarPersistentes(persistentes)
    if (restaurar.length) setToasts((atuais) => [...atuais, ...restaurar])

    const ref = timers.current
    return () => Object.values(ref).forEach(clearTimeout)
  }, [])

  return (
    <ToastContext.Provider value={{ mostrarNotificacao }}>
      {children}
      <div
        id="notificacoes-container"
        className="position-fixed bottom-0 end-0 p-3"
        style={{ zIndex: 5000 }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast align-items-center text-white bg-${t.tipo} fade show`}
            role="alert"
            aria-live="assertive"
            aria-atomic="true"
          >
            <div className="d-flex">
              <div className="toast-body">
                <i className={`${ICONES[t.tipo]} me-2`} /> {t.mensagem}
              </div>
              <button
                type="button"
                className="btn-close me-2 m-auto"
                aria-label="Fechar"
                onClick={() => (t.persistente ? fecharPersistente(t.id) : remover(t.id))}
              />
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
