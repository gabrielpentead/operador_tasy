/**
 * Porte fiel do bloco HEALTH MONITORING de dashboard.js.
 * Limiares e cores idênticos aos da versão atual.
 */

export const HEALTH_THRESHOLDS = {
  atencao: { ram: 85, disco: 85, temperatura: 75 },
  critico: { ram: 95, disco: 95, temperatura: 85 },
}

export function nivelClasse(nivel) {
  if (nivel === 'Crítico') return 'critico'
  if (nivel === 'Atenção') return 'atencao'
  return 'normal'
}

export function nivelIcone(nivel) {
  if (nivel === 'Crítico') return 'bi-exclamation-octagon-fill'
  if (nivel === 'Atenção') return 'bi-exclamation-triangle-fill'
  return 'bi-check-circle-fill'
}

/**
 * Devolve { colorCls, iconCls } de uma métrica, com a MESMA regra do original:
 * apenas ram, disco e temperatura têm limiares; cpu fica sempre em verde.
 */
export function metricaEstilo(campo, valor) {
  const thr = HEALTH_THRESHOLDS
  let colorCls = 'text-success'
  let iconCls = 'bi-check-circle-fill text-success'

  if (campo === 'ram' || campo === 'disco') {
    if (valor >= thr.critico[campo]) {
      colorCls = 'text-danger'
      iconCls = 'bi-exclamation-octagon-fill text-danger'
    } else if (valor >= thr.atencao[campo]) {
      colorCls = 'text-warning'
      iconCls = 'bi-exclamation-triangle-fill text-warning'
    }
  } else if (campo === 'temperatura' && valor > 0) {
    if (valor >= thr.critico.temperatura) {
      colorCls = 'text-danger'
      iconCls = 'bi-exclamation-octagon-fill text-danger'
    } else if (valor >= thr.atencao.temperatura) {
      colorCls = 'text-warning'
      iconCls = 'bi-exclamation-triangle-fill text-warning'
    }
  }
  return { colorCls, iconCls }
}

/** Cor das barras do card do servidor — mesma lógica de _setBar(). */
export function corPorLimiar(valor, corPadrao, limiares) {
  let cor = corPadrao
  ;(limiares || []).forEach(([at, c]) => {
    if (valor >= at) cor = c
  })
  return cor
}
