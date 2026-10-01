import { useAcessibilidade } from '../../context/AcessibilidadeContext'

/**
 * Configurações de acessibilidade. Disponível para qualquer usuário (não é
 * restrita a administrador) — são preferências pessoais deste navegador.
 */
export default function SecaoAcessibilidade() {
  const { libras, setLibras } = useAcessibilidade()

  return (
    <div>
      <h5 className="mb-1">Acessibilidade</h5>
      <p className="text-muted small mb-4">
        Recursos para tornar o painel mais acessível. As preferências valem para
        este navegador e podem ser ligadas ou desligadas a qualquer momento.
      </p>

      <div className="d-flex align-items-start justify-content-between border rounded p-3">
        <div className="me-3">
          <label htmlFor="sw-libras" className="fw-semibold d-block mb-1">
            <i className="bi bi-person-arms-up me-2" />Tradução em Libras (VLibras)
          </label>
          <p className="text-muted small mb-0">
            Ativa o avatar do <strong>VLibras</strong>, que traduz o texto da tela para a
            Língua Brasileira de Sinais. Um botão azul aparece no canto da tela para
            abrir o tradutor.
          </p>
        </div>
        <div className="form-check form-switch fs-4 flex-shrink-0">
          <input
            id="sw-libras"
            className="form-check-input"
            type="checkbox"
            role="switch"
            checked={libras}
            onChange={(e) => setLibras(e.target.checked)}
            aria-label="Ativar tradução em Libras"
          />
        </div>
      </div>
    </div>
  )
}
