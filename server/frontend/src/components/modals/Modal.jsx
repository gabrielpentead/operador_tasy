import { useEffect } from 'react'
import { createPortal } from 'react-dom'

/**
 * Base de modal. Reproduz a marcação e as classes do Bootstrap 5 (.modal,
 * .modal-dialog, .modal-content, .modal-backdrop) para que o style.css e o
 * CSS do Bootstrap continuem valendo sem alteração.
 *
 * O JS do Bootstrap não é usado: o ciclo de vida passa a ser do React. O
 * resultado visual é o mesmo, incluindo o backdrop e o bloqueio de rolagem.
 */
export default function Modal({
  aberto, onFechar, titulo, icone, children, rodape,
  tamanho = '', centralizado = false, headerClass = '',
}) {
  useEffect(() => {
    if (!aberto) return undefined
    // Bloqueia a rolagem do body, como o Bootstrap faz
    document.body.classList.add('modal-open')
    const onEsc = (e) => { if (e.key === 'Escape') onFechar() }
    document.addEventListener('keydown', onEsc)
    return () => {
      document.body.classList.remove('modal-open')
      document.removeEventListener('keydown', onEsc)
    }
  }, [aberto, onFechar])

  if (!aberto) return null

  return createPortal(
    <>
      <div
        className="modal fade show"
        style={{ display: 'block' }}
        tabIndex="-1"
        role="dialog"
        onMouseDown={(e) => { if (e.target === e.currentTarget) onFechar() }}
      >
        <div
          className={`modal-dialog${tamanho ? ` ${tamanho}` : ''}${centralizado ? ' modal-dialog-centered' : ''}`}
        >
          <div className="modal-content">
            <div className={`modal-header${headerClass ? ` ${headerClass}` : ''}`}>
              <h5 className="modal-title">
                {icone && <i className={`bi ${icone}`} />} {titulo}
              </h5>
              <button
                type="button"
                className={`btn-close${headerClass.includes('text-white') ? ' btn-close-white' : ''}`}
                aria-label="Fechar"
                onClick={onFechar}
              />
            </div>
            <div className="modal-body">{children}</div>
            {rodape && <div className="modal-footer">{rodape}</div>}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>,
    document.body
  )
}
