import { useState, useEffect, useRef } from 'react'
import Modal from './Modal'

/**
 * Cadastro/edição de um destinatário de alerta crítico.
 * onSalvar(dados) deve devolver {} em sucesso ou { erro } para exibir.
 */
export default function ModalDestinatario({ aberto, destinatario, onFechar, onSalvar }) {
  const editando = Boolean(destinatario)
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [ativo, setAtivo] = useState(true)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)
  const primeiroRef = useRef(null)

  useEffect(() => {
    if (!aberto) return
    setNome(destinatario?.nome || '')
    setEmail(destinatario?.email || '')
    setAtivo(destinatario ? !!destinatario.ativo : true)
    setErro(''); setSalvando(false)
    setTimeout(() => primeiroRef.current?.focus(), 60)
  }, [aberto, destinatario])

  const salvar = async () => {
    const valor = email.trim()
    if (!valor) { setErro('Informe o e-mail'); return }
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(valor)) { setErro('E-mail inválido'); return }

    setSalvando(true); setErro('')
    const r = await onSalvar({
      nome: nome.trim(),
      email: valor,
      ativo,
    })
    if (r?.erro) { setErro(r.erro); setSalvando(false) }
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={editando ? 'Editar destinatário' : 'Novo destinatário'}
      icone="bi-envelope-plus"
      centralizado
      rodape={
        <>
          <button type="button" className="btn btn-secondary" onClick={onFechar} disabled={salvando}>
            Cancelar
          </button>
          <button type="button" className="btn btn-primary" onClick={salvar} disabled={salvando}>
            {salvando
              ? <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Salvando…</>
              : 'Salvar'}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label className="form-label">Nome <span className="text-muted">(opcional)</span></label>
        <input ref={primeiroRef} type="text" className="form-control" value={nome}
               placeholder="Ex.: Plantão NTI"
               onChange={(e) => { setNome(e.target.value); setErro('') }} disabled={salvando} />
      </div>

      <div className="mb-3">
        <label className="form-label">E-mail</label>
        <div className="input-group">
          <span className="input-group-text"><i className="bi bi-envelope" /></span>
          <input type="email" className="form-control" value={email}
                 placeholder="plantao@hospitalsaovicente.org.br"
                 onChange={(e) => { setEmail(e.target.value); setErro('') }}
                 onKeyDown={(e) => { if (e.key === 'Enter') salvar() }} disabled={salvando} />
        </div>
      </div>

      <div className="form-check form-switch">
        <input className="form-check-input" type="checkbox" id="dest-ativo"
               checked={ativo} onChange={(e) => setAtivo(e.target.checked)} disabled={salvando} />
        <label className="form-check-label" htmlFor="dest-ativo">
          Ativo <span className="text-muted small">— desmarque para pausar o recebimento sem excluir</span>
        </label>
      </div>

      {erro && (
        <div className="alert alert-danger py-2 mt-3 mb-0 small" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2" />{erro}
        </div>
      )}
    </Modal>
  )
}
