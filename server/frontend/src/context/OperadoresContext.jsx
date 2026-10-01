import {
  createContext, useContext, useState, useEffect, useCallback, useRef,
} from 'react'
import { socket, EVENTOS } from '../services/socket'
import * as api from '../services/api'
import { useToast } from './ToastContext'
import { useNotificacoes } from './NotificacoesContext'

/**
 * Núcleo de dados. Reúne o que estava espalhado entre common.js
 * (conexão, polling, overlay) e dashboard.js (carga e eventos).
 *
 * Comportamento preservado:
 *  - polling de 30 s (CONFIG.intervaloAtualizacao) somente enquanto conectado
 *  - ao (re)conectar, recarrega imediatamente
 *  - overlay de servidor indisponível, exceto em desconexão intencional
 *    ('io client disconnect'), igual ao original
 *  - status_operador faz merge parcial no operador (Object.assign do original),
 *    não substituição — campos ausentes no evento são mantidos
 *  - toast de "Ponto Offline" dispara UMA vez por operador, 30 s após ficar
 *    offline, e é cancelado se ele voltar antes disso
 */

const OperadoresContext = createContext(null)
export const useOperadores = () => useContext(OperadoresContext)

const POLLING_DELAY_ONLINE = 30000
const OFFLINE_TOAST_DELAY = 30000

export function OperadoresProvider({ children }) {
  const [operadores, setOperadores] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [conectado, setConectado] = useState(false)
  const [servidorOffline, setServidorOffline] = useState(false)
  const [toastsOffline, setToastsOffline] = useState([])

  const { mostrarNotificacao } = useToast()
  const notif = useNotificacoes()

  // Espelho do estado para uso dentro de handlers do socket sem recriar listeners
  const operadoresRef = useRef([])
  useEffect(() => { operadoresRef.current = operadores }, [operadores])

  // Controle do toast de offline — porte de _offlineState
  const offlineCtl = useRef({ timers: {}, pingFired: new Set() })
  const conectadoRef = useRef(false)
  useEffect(() => { conectadoRef.current = conectado }, [conectado])

  /* ── Carga de operadores ─────────────────────────────────────── */
  const carregarOperadores = useCallback(async () => {
    try {
      const data = await api.listarOperadores()
      if (data.success) {
        setOperadores(data.operadores || [])
        notif.inicializarEstadoBase(data.operadores || [])
      } else {
        mostrarNotificacao(`Erro ao carregar operadores: ${data.error}`, 'danger')
      }
    } catch (error) {
      mostrarNotificacao(`Erro de conexão ao carregar operadores: ${error.message}`, 'danger')
    } finally {
      setCarregando(false)
    }
  }, [mostrarNotificacao, notif])

  const carregarRef = useRef(carregarOperadores)
  useEffect(() => { carregarRef.current = carregarOperadores }, [carregarOperadores])

  /* ── Toast de "Ponto Offline" ────────────────────────────────── */
  const dispararToastOffline = useCallback((nome) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    setToastsOffline((t) => [{ id, nome }, ...t])
    setTimeout(() => setToastsOffline((t) => t.filter((x) => x.id !== id)), 8000)
  }, [])

  const fecharToastOffline = useCallback(
    (id) => setToastsOffline((t) => t.filter((x) => x.id !== id)),
    []
  )

  const tratarTransicaoOffline = useCallback(
    (operadorId, isOnline, nome) => {
      const ctl = offlineCtl.current
      if (!isOnline) {
        if (!ctl.timers[operadorId] && !ctl.pingFired.has(operadorId)) {
          ctl.timers[operadorId] = setTimeout(() => {
            ctl.pingFired.add(operadorId)
            delete ctl.timers[operadorId]
            dispararToastOffline(nome || operadorId)
          }, OFFLINE_TOAST_DELAY)
        }
      } else {
        ctl.pingFired.delete(operadorId)
        if (ctl.timers[operadorId]) {
          clearTimeout(ctl.timers[operadorId])
          delete ctl.timers[operadorId]
        }
      }
    },
    [dispararToastOffline]
  )

  /* ── Eventos do WebSocket ────────────────────────────────────── */
  useEffect(() => {
    const onConnect = () => {
      setConectado(true)
      setServidorOffline(false)
      carregarRef.current()
    }

    const onDisconnect = (reason) => {
      setConectado(false)
      // Desconexão intencional não mostra overlay — regra do original
      if (reason !== 'io client disconnect') setServidorOffline(true)
    }

    const onConnectError = () => {
      setConectado(false)
      setServidorOffline(true)
    }

    const onStatusOperador = (data) => {
      if (!data || !data.id) return
      // O backend manda 'nome' no próprio evento (fonte confiável). O cache
      // local (operadoresRef) só entra como reforço: sem ele, num reconnect
      // em massa logo após o servidor subir, o REST que popula esse cache
      // podia ainda não ter terminado quando o evento chegava, e a
      // notificação saía com o id em vez do nome.
      const existente = operadoresRef.current.find((op) => op.id === data.id)
      const nome = data.nome || existente?.nome || data.id
      setOperadores((atuais) => {
        const idx = atuais.findIndex((op) => op.id === data.id)
        if (idx === -1) return atuais
        const copia = [...atuais]
        // Merge parcial, equivalente ao Object.assign do original
        copia[idx] = { ...copia[idx], ...data }
        return copia
      })
      notif.checarMudancaOnline(data.id, !!data.online, nome)
      tratarTransicaoOffline(data.id, !!data.online, nome)
    }

    const onSaudeAtualizada = (data) => {
      if (!data || !data.id) return
      const existente = operadoresRef.current.find((op) => op.id === data.id)
      const nome = data.nome || existente?.nome || data.id
      setOperadores((atuais) => {
        const idx = atuais.findIndex((op) => op.id === data.id)
        if (idx === -1) return atuais
        const copia = [...atuais]
        copia[idx] = {
          ...copia[idx],
          saude: data.saude,
          nivel_saude: data.nivel,
          motivos: data.motivos || [],
        }
        return copia
      })
      notif.checarMudancaSaude(data.id, data.nivel, data.motivos, nome)
    }

    const onOperadorAdicionado = () => {
      mostrarNotificacao('Novo operador adicionado', 'success')
      carregarRef.current()
    }
    const onOperadorRemovido = () => {
      mostrarNotificacao('Operador removido', 'info')
      carregarRef.current()
    }
    const onComandoRecebido = (data) => {
      mostrarNotificacao(`Comando '${data.comando}' recebido pelo operador.`, 'info')
    }
    const onResultadoComando = (data) => {
      const tipo = data.sucesso ? 'success' : 'danger'
      const icone = data.sucesso ? '✅' : '❌'
      mostrarNotificacao(`${icone} ${data.mensagem}`, tipo)
      carregarRef.current()
    }
    const onConfigAlterada = (data) => {
      mostrarNotificacao(
        'Configurações do servidor alteradas. Aguarde o reinício do servidor...',
        'warning', 0, true
      )
      setTimeout(() => {
        window.location.href = `http://${data.host}:${data.port}${window.location.pathname}`
      }, 5000)
    }

    socket.on(EVENTOS.CONNECT, onConnect)
    socket.on(EVENTOS.DISCONNECT, onDisconnect)
    socket.on(EVENTOS.CONNECT_ERROR, onConnectError)
    socket.on(EVENTOS.STATUS_OPERADOR, onStatusOperador)
    socket.on(EVENTOS.SAUDE_ATUALIZADA, onSaudeAtualizada)
    socket.on(EVENTOS.OPERADOR_ADICIONADO, onOperadorAdicionado)
    socket.on(EVENTOS.OPERADOR_REMOVIDO, onOperadorRemovido)
    socket.on(EVENTOS.COMANDO_RECEBIDO, onComandoRecebido)
    socket.on(EVENTOS.RESULTADO_COMANDO, onResultadoComando)
    socket.on(EVENTOS.SERVIDOR_CONFIG_ALTERADA, onConfigAlterada)

    // Se o socket já estava conectado quando o componente montou
    if (socket.connected) onConnect()

    const ctl = offlineCtl.current
    return () => {
      socket.off(EVENTOS.CONNECT, onConnect)
      socket.off(EVENTOS.DISCONNECT, onDisconnect)
      socket.off(EVENTOS.CONNECT_ERROR, onConnectError)
      socket.off(EVENTOS.STATUS_OPERADOR, onStatusOperador)
      socket.off(EVENTOS.SAUDE_ATUALIZADA, onSaudeAtualizada)
      socket.off(EVENTOS.OPERADOR_ADICIONADO, onOperadorAdicionado)
      socket.off(EVENTOS.OPERADOR_REMOVIDO, onOperadorRemovido)
      socket.off(EVENTOS.COMANDO_RECEBIDO, onComandoRecebido)
      socket.off(EVENTOS.RESULTADO_COMANDO, onResultadoComando)
      socket.off(EVENTOS.SERVIDOR_CONFIG_ALTERADA, onConfigAlterada)
      Object.values(ctl.timers).forEach(clearTimeout)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* ── Carga inicial ───────────────────────────────────────────
     O original chamava carregarOperadores() no DOMContentLoaded, sem depender
     do socket. Reproduzido aqui: a lista aparece mesmo que o WebSocket ainda
     não tenha conectado. */
  useEffect(() => {
    carregarRef.current()
  }, [])

  /* ── Polling de 30 s, apenas enquanto conectado ──────────────── */
  useEffect(() => {
    if (!conectado) return undefined
    const t = setInterval(() => {
      if (conectadoRef.current) carregarRef.current()
    }, POLLING_DELAY_ONLINE)
    return () => clearInterval(t)
  }, [conectado])

  return (
    <OperadoresContext.Provider
      value={{
        operadores, carregando, conectado, servidorOffline,
        carregarOperadores, toastsOffline, fecharToastOffline,
      }}
    >
      {children}
    </OperadoresContext.Provider>
  )
}
