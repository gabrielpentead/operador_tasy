import { useState, useEffect, useRef } from 'react'
import Modal from './Modal'

/**
 * "Esqueci minha senha" — pede o e-mail e dispara o envio do link.
 *
 * A resposta do servidor é propositalmente a mesma exista ou não a conta, para
 * não revelar quais e-mails têm cadastro. A tela reflete isso: mostra sempre a
 * mesma confirmação, sem afirmar que o endereço existe.
 */
export default function ModalEsqueciSenha({ aberto, onFechar, onEnviar }) {
  const [email, setEmail] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [enviado, setEnviado] = useState(false)
  const campoRef = useRef(null)

  useEffect(() => {
    if (!aberto) return
    setEmail(''); setErro(''); setEnviando(false); setEnviado(false)
    setTimeout(() => campoRef.current?.focus(), 60)
  }, [aberto])

  const enviar = async () => {
    const valor = email.trim()
    if (!valor) { setErro('Informe seu e-mail'); return }
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(valor)) { setErro('E-mail inválido'); return }

    setEnviando(true); setErro('')
    const r = await onEnviar(valor)
    if (r?.erro) { setErro(r.erro); setEnviando(false) }
    else { setEnviado(true); setEnviando(false) }
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo="Redefinir senha"
      icone="bi-key"
      centralizado
      rodape={enviado ? (
        <button type="button" className="btn btn-primary w-100" onClick={onFechar}>Fechar</button>
      ) : (
        <>
          <button type="button" className="btn btn-secondary" onClick={onFechar} disabled={enviando}>
            Cancelar
          </button>
          <button type="button" className="btn btn-primary" onClick={enviar} disabled={enviando}>
            {enviando
              ? <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Enviando…</>
              : 'Enviar link'}
          </button>
        </>
      )}
    >
      {enviado ? (
        <div className="text-center py-2">
          <i className="bi bi-envelope-check text-success" style={{ fontSize: '2.5rem' }} />
          <p className="mt-3 mb-0">
            Se este e-mail estiver cadastrado, enviamos um link para redefinir a senha.
          </p>
          <p className="small text-muted mt-2 mb-0">
            O link vale por 60 minutos. Verifique também a caixa de spam.
          </p>
        </div>
      ) : (
        <>
          <p className="small text-muted">
            Informe o e-mail cadastrado. Enviaremos um link para você escolher uma nova senha.
          </p>
          <div className="input-group">
            <span className="input-group-text"><i className="bi bi-envelope" /></span>
            <input
              ref={campoRef}
              type="email"
              className="form-control"
              value={email}
              placeholder="seu.email@exemplo.com"
              onChange={(e) => { setEmail(e.target.value); setErro('') }}
              onKeyDown={(e) => { if (e.key === 'Enter') enviar() }}
              disabled={enviando}
            />
          </div>
          {erro && (
            <div className="alert alert-danger py-2 mt-3 mb-0 small" role="alert">
              <i className="bi bi-exclamation-triangle-fill me-2" />{erro}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}
