/**
 * Porte fiel de dashboard.js — isPartRunning() e getAutomationStatus().
 * A lógica NÃO foi alterada: mesmos estados de parada, mesmo tratamento
 * de status como string ou objeto, mesmo fallback para o tipo "Ambos".
 */

export function isPartRunning(status) {
  if (typeof status !== 'string' || !status) return false
  const lowerStatus = status.toLowerCase()
  // A automação está rodando se o status NÃO for um dos estados de parada explícitos.
  const stoppedStates = ['parado', 'erro', 'desconectado', 'inicializado']
  return !stoppedStates.some((s) => lowerStatus.includes(s))
}

export function getAutomationStatus(operador) {
  const status = {
    monitor: { isRunning: false, text: 'Parado' },
    totem: { isRunning: false, text: 'Parado' },
  }

  if (!operador || !operador.online || !operador.status) return status

  const opStatus = operador.status

  if (operador.tipo_cadastro === 'Monitor de Senhas') {
    const statusText =
      typeof opStatus === 'object' && opStatus !== null ? opStatus.monitor : opStatus
    status.monitor.text = statusText || 'Parado'
    status.monitor.isRunning = isPartRunning(status.monitor.text)
  } else if (operador.tipo_cadastro === 'Totem de Senhas') {
    const statusText =
      typeof opStatus === 'object' && opStatus !== null ? opStatus.totem : opStatus
    status.totem.text = statusText || 'Parado'
    status.totem.isRunning = isPartRunning(status.totem.text)
  } else if (operador.tipo_cadastro === 'Ambos') {
    if (typeof opStatus === 'object' && opStatus !== null) {
      status.monitor.text = opStatus.monitor || 'Parado'
      status.monitor.isRunning = isPartRunning(status.monitor.text)
      status.totem.text = opStatus.totem || 'Parado'
      status.totem.isRunning = isPartRunning(status.totem.text)
    } else {
      // Fallback quando o status vem como string única para o tipo "Ambos"
      const statusText = typeof opStatus === 'string' ? opStatus : 'Indefinido'
      const isRunning = isPartRunning(statusText)
      status.monitor.text = statusText
      status.monitor.isRunning = isRunning
      status.totem.text = statusText
      status.totem.isRunning = isRunning
    }
  }
  return status
}

/** Contadores dos cards de topo — porte de atualizarContadores(). */
export function calcularContadores(operadores) {
  let totalMonitores = 0, onlineMonitores = 0, iniciadosMonitores = 0
  let totalTotens = 0, onlineTotens = 0, iniciadosTotens = 0

  ;(operadores || []).forEach((op) => {
    const automationStatus = getAutomationStatus(op)
    const isMonitorType =
      op.tipo_cadastro === 'Monitor de Senhas' || op.tipo_cadastro === 'Ambos'
    const isTotemType =
      op.tipo_cadastro === 'Totem de Senhas' || op.tipo_cadastro === 'Ambos'

    if (isMonitorType) {
      totalMonitores++
      if (op.online) {
        onlineMonitores++
        if (automationStatus.monitor.isRunning) iniciadosMonitores++
      }
    }
    if (isTotemType) {
      totalTotens++
      if (op.online) {
        onlineTotens++
        if (automationStatus.totem.isRunning) iniciadosTotens++
      }
    }
  })

  return {
    monitores: {
      cadastrados: totalMonitores,
      online: onlineMonitores,
      offline: totalMonitores - onlineMonitores,
      iniciados: iniciadosMonitores,
      parados: onlineMonitores - iniciadosMonitores,
    },
    totens: {
      cadastrados: totalTotens,
      online: onlineTotens,
      offline: totalTotens - onlineTotens,
      iniciados: iniciadosTotens,
      parados: onlineTotens - iniciadosTotens,
    },
  }
}
