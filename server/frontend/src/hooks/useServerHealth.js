import { useState, useEffect, useCallback } from 'react'
import { obterSaudeServidor } from '../services/api'

/**
 * Porte do bloco de health check embutido no <script> do index.html.
 * Mantém o intervalo de 15 s e os três estados de badge do original:
 * 'Online' (sucesso), 'Erro' (success:false) e 'Sem dados' (falha de rede).
 */
const INTERVALO = 15000

export function useServerHealth() {
  const [saude, setSaude] = useState(null)
  const [badge, setBadge] = useState({ cls: 'bg-success', texto: 'Online' })
  const [erro, setErro] = useState(null)
  const [atualizadoEm, setAtualizadoEm] = useState(null)

  const atualizar = useCallback(async () => {
    try {
      const data = await obterSaudeServidor()
      if (!data.success) {
        setErro(data.error || 'Erro desconhecido')
        setBadge({ cls: 'bg-danger', texto: 'Erro' })
        return
      }
      setErro(null)
      setSaude(data.saude)
      setAtualizadoEm(new Date())
      setBadge({ cls: 'bg-success', texto: 'Online' })
    } catch {
      setBadge({ cls: 'bg-secondary', texto: 'Sem dados' })
    }
  }, [])

  useEffect(() => {
    atualizar()
    const t = setInterval(atualizar, INTERVALO)
    return () => clearInterval(t)
  }, [atualizar])

  return { saude, badge, erro, atualizadoEm }
}
