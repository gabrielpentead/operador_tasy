import { useState, useEffect, useRef } from 'react'
import Modal from './Modal'

// Convenção igual à do Python datetime.weekday() usado no agendador do
// servidor (monitoring/restart_scheduler.py): 0=segunda .. 6=domingo. NÃO usar
// a convenção do JS Date.getDay() (0=domingo) aqui — foi o que fez os
// agendamentos disparoravem no dia errado antes desta correção.
const DIAS = [
  { valor: 0, rotulo: 'Seg' },
  { valor: 1, rotulo: 'Ter' },
  { valor: 2, rotulo: 'Qua' },
  { valor: 3, rotulo: 'Qui' },
  { valor: 4, rotulo: 'Sex' },
  { valor: 5, rotulo: 'Sáb' },
  { valor: 6, rotulo: 'Dom' },
]
const TODOS_OS_DIAS = DIAS.map((d) => d.valor)

/**
 * Cadastro/edição de um agendamento de reinício automático dos painéis.
 * onSalvar(dados) deve devolver {} em sucesso ou { erro } para exibir.
 */
export default function ModalReinicioProgramado({ aberto, reinicio, onFechar, onSalvar }) {
  const editando = Boolean(reinicio)
  const [horario, setHorario] = useState('06:50')
  const [dias, setDias] = useState(TODOS_OS_DIAS)
  const [target, setTarget] = useState('ambos')
  const [descricao, setDescricao] = useState('')
  const [ativo, setAtivo] = useState(true)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)
  const primeiroRef = useRef(null)

  useEffect(() => {
    if (!aberto) return
    setHorario(reinicio?.horario || '06:50')
    setDias(reinicio ? reinicio.dias_semana : TODOS_OS_DIAS)
    setTarget(reinicio?.target || 'ambos')
    setDescricao(reinicio?.descricao || '')
    setAtivo(reinicio ? !!reinicio.ativo : true)
    setErro(''); setSalvando(false)
    setTimeout(() => primeiroRef.current?.focus(), 60)
  }, [aberto, reinicio])

  const alternarDia = (valor) => {
    setDias((atual) => atual.includes(valor)
      ? atual.filter((d) => d !== valor)
      : [...atual, valor].sort())
    setErro('')
  }

  const salvar = async () => {
    if (!/^([01]\d|2[0-3]):([0-5]\d)$/.test(horario)) { setErro('Horário inválido'); return }
    if (dias.length === 0) { setErro('Selecione ao menos um dia da semana'); return }

    setSalvando(true); setErro('')
    const r = await onSalvar({
      horario,
      dias_semana: dias,
      target,
      descricao: descricao.trim(),
      ativo,
    })
    if (r?.erro) { setErro(r.erro); setSalvando(false) }
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={editando ? 'Editar reinício programado' : 'Novo reinício programado'}
      icone="bi-arrow-repeat"
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
        <label className="form-label">Horário</label>
        <input ref={primeiroRef} type="time" className="form-control" value={horario}
               onChange={(e) => { setHorario(e.target.value); setErro('') }} disabled={salvando} />
      </div>

      <div className="mb-3">
        <label className="form-label d-block">Dias da semana</label>
        <div className="d-flex flex-wrap gap-2">
          {DIAS.map((d) => (
            <button
              key={d.valor}
              type="button"
              className={`btn btn-sm rounded-pill dia-semana-btn ${dias.includes(d.valor) ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => alternarDia(d.valor)}
              disabled={salvando}
            >
              {d.rotulo}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3">
        <label className="form-label">Alvo</label>
        <select className="form-select" value={target} disabled={salvando}
                onChange={(e) => setTarget(e.target.value)}>
          <option value="ambos">Ambos (Monitor e Totem)</option>
          <option value="monitor">Apenas Monitor</option>
          <option value="totem">Apenas Totem</option>
        </select>
      </div>

      <div className="mb-3">
        <label className="form-label">Descrição <span className="text-muted">(opcional)</span></label>
        <input type="text" className="form-control" value={descricao}
               placeholder="Ex.: Reinício da madrugada"
               onChange={(e) => setDescricao(e.target.value)} disabled={salvando} />
      </div>

      <div className="form-check form-switch">
        <input className="form-check-input" type="checkbox" id="reinicio-ativo"
               checked={ativo} onChange={(e) => setAtivo(e.target.checked)} disabled={salvando} />
        <label className="form-check-label" htmlFor="reinicio-ativo">
          Ativo <span className="text-muted small">— desmarque para pausar sem excluir</span>
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
