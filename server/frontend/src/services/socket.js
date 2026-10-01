import { io } from 'socket.io-client'

/**
 * Instância única do Socket.IO.
 *
 * Os parâmetros de reconexão são os MESMOS de common.js — foram mantidos
 * porque estavam ajustados para "evitar spam" segundo o comentário original:
 *   reconnection: true, delay 2000, delayMax 5000, tentativas infinitas, timeout 10000
 */
export const socket = io({
  reconnection: true,
  reconnectionDelay: 2000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: Infinity,
  timeout: 10000,
  autoConnect: true,
})

/** Eventos emitidos pelo servidor (routes/websocket.py). */
export const EVENTOS = {
  CONNECT: 'connect',
  DISCONNECT: 'disconnect',
  CONNECT_ERROR: 'connect_error',
  STATUS_OPERADOR: 'status_operador',
  OPERADOR_ADICIONADO: 'operador_adicionado',
  OPERADOR_REMOVIDO: 'operador_removido',
  SAUDE_ATUALIZADA: 'saude_atualizada',
  EVENTOS_ATUALIZADOS: 'eventos_atualizados',
  COMANDO_RECEBIDO: 'comando_recebido',
  RESULTADO_COMANDO: 'resultado_comando',
  SERVIDOR_CONFIG_ALTERADA: 'servidor_config_alterada',
}
