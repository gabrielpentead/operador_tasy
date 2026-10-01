import Modal from './Modal'

/** Porte de confirmarExclusao() — mesmo texto, mesmo alerta, mesmas classes.
 *  `mensagem` (opcional) substitui a frase padrão para reaproveitar em outras
 *  exclusões (ex.: destinatários de alerta). Sem ela, o comportamento é o mesmo. */
export default function ModalConfirmarExclusao({ aberto, operador, onFechar, onConfirmar, mensagem }) {
  const rodape = (
    <>
      <button type="button" className="btn btn-secondary" onClick={onFechar}>Cancelar</button>
      <button type="button" className="btn btn-danger" onClick={onConfirmar}>
        Excluir Permanentemente
      </button>
    </>
  )

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo="Confirmar Exclusão"
      icone="bi-exclamation-triangle"
      headerClass="bg-danger text-white"
      rodape={rodape}
    >
      <div className="text-center mb-4">
        <i className="bi bi-trash text-danger" style={{ fontSize: '3rem' }} />
      </div>
      <p className="text-center">
        {mensagem || <>Tem certeza que deseja excluir o operador <strong>{operador?.nome}</strong>?</>}
      </p>
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle-fill" /> Esta ação não pode ser desfeita.
      </div>
    </Modal>
  )
}
