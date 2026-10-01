/**
 * Porte de common.js — formatarData(), tempoRelativo() e formatBytes().
 *
 * escapeHtml() NÃO foi portado de propósito: o React escapa por padrão ao
 * interpolar texto em JSX, então a proteção contra XSS que o original obtinha
 * chamando escapeHtml() manualmente passa a ser automática. Nenhum componente
 * usa dangerouslySetInnerHTML com dado vindo do servidor.
 */

export function formatarData(dataString) {
  if (!dataString) return '-'
  try {
    const data = new Date(dataString)
    return data.toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch {
    return dataString
  }
}

export function tempoRelativo(dataString) {
  if (!dataString) return ''
  try {
    const data = new Date(dataString)
    const agora = new Date()
    const diff = Math.floor((agora - data) / 1000)

    if (diff < 30) return 'agora mesmo'
    if (diff < 60) return `há ${diff} segundos`
    if (diff < 3600) {
      const minutos = Math.floor(diff / 60)
      return `há ${minutos} ${minutos === 1 ? 'minuto' : 'minutos'}`
    }
    if (diff < 86400) {
      const horas = Math.floor(diff / 3600)
      return `há ${horas} ${horas === 1 ? 'hora' : 'horas'}`
    }
    const dias = Math.floor(diff / 86400)
    return `há ${dias} ${dias === 1 ? 'dia' : 'dias'}`
  } catch {
    return ''
  }
}

export function formatBytes(used, total) {
  return `${used} GB / ${total} GB`
}

/** Timestamp curto usado no card do servidor e nas notificações. */
export function horaCurta(date = new Date()) {
  return date.toLocaleTimeString('pt-BR')
}

/** Porte de _notifRelTime() da central de notificações. */
export function notifRelTime(iso) {
  try {
    const d = new Date(iso)
    const abs = d.toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
    const s = Math.floor((Date.now() - d.getTime()) / 1000)
    let rel = ''
    if (s < 60) rel = 'agora mesmo'
    else if (s < 3600) rel = `há ${Math.floor(s / 60)} min`
    else if (s < 86400) rel = `há ${Math.floor(s / 3600)} h`
    return rel ? `${abs} · ${rel}` : abs
  } catch {
    return ''
  }
}
