import { useState } from 'react'
import SecaoUsuarios from '../components/configuracoes/SecaoUsuarios'
import SecaoAlertas from '../components/configuracoes/SecaoAlertas'
import SecaoReinicios from '../components/configuracoes/SecaoReinicios'
import SecaoAcessibilidade from '../components/configuracoes/SecaoAcessibilidade'

/**
 * Página de Configurações.
 *
 * Estruturada para crescer: cada área é uma entrada em SECOES, com o
 * componente que a desenha. Para acrescentar uma configuração nova no futuro,
 * basta criar o componente da seção e somar um item nesta lista — a navegação
 * lateral, o título e o roteamento interno se ajustam sozinhos.
 */
const SECOES = [
  {
    id: 'usuarios',
    rotulo: 'Usuários',
    icone: 'bi-people',
    descricao: 'Acesso ao painel e permissões',
    componente: SecaoUsuarios,
    somenteAdmin: true,
  },
  {
    id: 'alertas',
    rotulo: 'Alertas',
    icone: 'bi-bell',
    descricao: 'E-mails de alertas críticos',
    componente: SecaoAlertas,
    somenteAdmin: true,
  },
  {
    id: 'reinicios',
    rotulo: 'Reinícios',
    icone: 'bi-arrow-repeat',
    descricao: 'Programação de reinício dos painéis',
    componente: SecaoReinicios,
    somenteAdmin: true,
  },
  {
    id: 'acessibilidade',
    rotulo: 'Acessibilidade',
    icone: 'bi-universal-access',
    descricao: 'Tradução em Libras (VLibras)',
    componente: SecaoAcessibilidade,
    somenteAdmin: false,
  },
]

export default function Configuracoes({ onVoltar, isAdmin }) {
  const disponiveis = SECOES.filter((s) => !s.somenteAdmin || isAdmin)
  const [ativa, setAtiva] = useState(disponiveis[0]?.id)

  const secao = disponiveis.find((s) => s.id === ativa) || disponiveis[0]
  const Conteudo = secao?.componente

  return (
    <div className="container config-pagina">
      <div className="config-topo">
        <button className="btn btn-outline-secondary btn-sm" onClick={onVoltar}>
          <i className="bi bi-arrow-left me-1" />Voltar ao painel
        </button>
        <div>
          <h4 className="config-titulo">
            <i className="bi bi-gear me-2" />Configurações
          </h4>
          <small className="text-muted">Central de Operadores — HSV</small>
        </div>
      </div>

      <div className="config-corpo">
        <nav className="config-nav" aria-label="Seções de configuração">
          {disponiveis.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`config-nav-item${s.id === ativa ? ' ativo' : ''}`}
              onClick={() => setAtiva(s.id)}
              aria-current={s.id === ativa ? 'page' : undefined}
            >
              <i className={`bi ${s.icone}`} />
              <span className="config-nav-texto">
                <span className="config-nav-rotulo">{s.rotulo}</span>
                <span className="config-nav-descricao">{s.descricao}</span>
              </span>
            </button>
          ))}
        </nav>

        <section className="config-conteudo">
          {Conteudo ? <Conteudo /> : (
            <p className="text-muted mb-0">Nenhuma configuração disponível para o seu perfil.</p>
          )}
        </section>
      </div>

      <footer className="mt-5 pt-4 pb-2 text-center text-muted">
        <p className="small">NTI - Núcleo de Tecnologia da Informação</p>
      </footer>
    </div>
  )
}
