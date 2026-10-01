import { useMemo } from 'react'
import { useOperadores } from '../../context/OperadoresContext'
import { calcularContadores } from '../../utils/status'

/**
 * Cards consolidados de Monitores e Totens. Marcação e classes idênticas ao
 * index.html original — os números vêm de calcularContadores(), que é o porte
 * literal de atualizarContadores().
 */

function Bloco({ titulo, imagem, alt, dados }) {
  const quadrantes = [
    { rotulo: 'Online', cor: 'success', valor: dados.online },
    { rotulo: 'Offline', cor: 'danger', valor: dados.offline },
    { rotulo: 'Iniciados', cor: 'info', valor: dados.iniciados },
    { rotulo: 'Parados', cor: 'warning', valor: dados.parados },
  ]

  return (
    <div className="col-lg-6 mb-4">
      <div className="card h-100 border-0 shadow-sm">
        <div className="card-header bg-white border-bottom-0 pt-4 pb-0 px-4">
          <div className="d-flex align-items-center justify-content-between">
            <div className="d-flex align-items-center">
              <div className="me-3 text-center" style={{ minWidth: 40 }}>
                <span className="d-block display-5 fw-bold text-dark lh-1">
                  {dados.cadastrados}
                </span>
              </div>
              <div className="border-start ps-3 py-1">
                <h4 className="card-title mb-0 fw-bold text-dark">{titulo}</h4>
                <small className="text-muted">Visão geral</small>
              </div>
            </div>
            <div className="rounded-circle bg-primary bg-opacity-10 p-3">
              <img src={imagem} alt={alt} width="24" height="24" />
            </div>
          </div>
        </div>
        <div className="card-body p-4">
          <div className="row g-3">
            {quadrantes.map((q) => (
              <div className="col-6" key={q.rotulo}>
                <div
                  className={`p-3 rounded-3 bg-${q.cor} bg-opacity-10 h-100 border border-${q.cor} border-opacity-25`}
                >
                  <span
                    className={`d-block text-${q.cor} small text-uppercase fw-semibold mb-2`}
                  >
                    {q.rotulo}
                  </span>
                  <span className={`d-block display-6 fw-bold text-${q.cor}`}>
                    {q.valor}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function StatusCards() {
  const { operadores } = useOperadores()
  const contadores = useMemo(() => calcularContadores(operadores), [operadores])

  return (
    <div className="row mb-4">
      <Bloco
        titulo="Monitores"
        imagem="/static/img/monitor.png"
        alt="Monitores"
        dados={contadores.monitores}
      />
      <Bloco
        titulo="Totens"
        imagem="/static/img/totem.png"
        alt="Totens"
        dados={contadores.totens}
      />
    </div>
  )
}
