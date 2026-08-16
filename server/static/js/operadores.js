/**
 * operadores.js - Funções específicas para a página de gerenciamento de operadores
 */

// Elementos DOM
let tabelaOperadores;
let carregandoOperadores;
let semOperadores;
let filtroOperador;

// Inicialização quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando página de operadores...');
    
    // Capturar elementos DOM
    tabelaOperadores = document.getElementById('tabela-operadores');
    carregandoOperadores = document.getElementById('carregando-operadores');
    semOperadores = document.getElementById('sem-operadores');
    filtroOperador = document.getElementById('filtro-operador');
    
    // Verificação para debug
    if (!semOperadores) {
        console.warn('Elemento #sem-operadores não encontrado na página');
    }
    
    // Carregar dados iniciais
    carregarOperadores();
    
    // Configurar eventos WebSocket específicos desta página
    configurarEventosWebSocket();
    
    // Configurar filtro
    filtroOperador.addEventListener('input', renderizarTabelaOperadores);
    
    // Configurar botões dos modais
    configurarEventosModais();

    // Configurar listener para o switch de credenciais separadas
    const switchCredenciais = document.getElementById('edit-usa_credenciais_separadas');
    if (switchCredenciais) {
        switchCredenciais.addEventListener('change', toggleCredenciaisEdicao);
    }
});

// Função para alternar visibilidade das credenciais no modal de edição
function toggleCredenciaisEdicao() {
    const checkbox = document.getElementById('edit-usa_credenciais_separadas');
    const sharedSection = document.getElementById('shared-credentials');
    const separateSection = document.getElementById('separate-credentials');
    
    if (checkbox && sharedSection && separateSection) {
        if (checkbox.checked) {
            sharedSection.style.display = 'none';
            separateSection.style.display = 'block';
            
            // Opcional: Limpar campos obrigatórios do compartilhado para evitar validação HTML se houver
            // Mas aqui estamos validando via JS
        } else {
            sharedSection.style.display = 'block';
            separateSection.style.display = 'none';
        }
    }
}

// Configurar eventos WebSocket específicos para a página de operadores
function configurarEventosWebSocket() {
    // Atualização de status de um operador
    socket.on('status_operador', function(data) {
        // Verificar se os dados recebidos são válidos
        if (!data || !data.id) {
            console.warn('Dados de status de operador inválidos', data);
            return;
        }
        
        // Atualizar dados do operador
        const index = dadosOperadores.findIndex(op => op.id === data.id);
        
        if (index !== -1) {
            // Atualizar propriedades online e status
            dadosOperadores[index].online = data.online;
            
            if (data.online) {
                dadosOperadores[index].status = data.status;
                dadosOperadores[index].ultima_atualizacao = data.ultima_atualizacao;
            }
            
            // Atualizar UI com tratamento de erro
            try {
                renderizarTabelaOperadores();
            } catch (error) {
                console.error('Erro ao renderizar tabela após atualização de status:', error);
            }
        }
    });
    
    // Operador adicionado
    socket.on('operador_adicionado', function(data) {
        // Verificar se os dados recebidos são válidos
        if (!data || !data.id) {
            console.warn('Dados de operador adicionado inválidos', data);
            return;
        }
        
        try {
            // Recarregar todos os operadores para garantir dados completos
            carregarOperadores();
            mostrarNotificacao('Novo operador adicionado', 'success', 5000, false);
        } catch (error) {
            console.error('Erro ao processar adição de operador:', error);
        }
    });
    
    // Operador removido
    socket.on('operador_removido', function(data) {
        // Verificar se os dados recebidos são válidos
        if (!data || !data.id) {
            console.warn('Dados de operador removido inválidos', data);
            return;
        }
        
        try {
            // Remover operador da lista local
            dadosOperadores = dadosOperadores.filter(op => op.id !== data.id);
            renderizarTabelaOperadores();
            
            // Verificar se o elemento semOperadores existe antes de manipulá-lo
            if (semOperadores && dadosOperadores.length === 0) {
                semOperadores.classList.remove('d-none');
            }
            
            mostrarNotificacao('Operador removido', 'info', 5000, false);
        } catch (error) {
            console.error('Erro ao processar remoção de operador:', error);
        }
    });
}

// Configurar eventos dos modais
function configurarEventosModais() {
    // Adicionar operador
    document.getElementById('btnSalvarOperador').addEventListener('click', adicionarOperador);
    
    // Atualizar operador
    document.getElementById('btnAtualizarOperador').addEventListener('click', atualizarOperador);
}

// Carregar dados dos operadores
async function carregarOperadores() {
    try {
        const response = await fetch('/api/operadores');
        const data = await response.json();
        
        if (data.success) {
            // Armazenar dados
            dadosOperadores = data.operadores;
            
            // Atualizar UI
            renderizarTabelaOperadores();
        } else {
            console.error('Erro ao carregar operadores:', data.error);
            mostrarNotificacao(`Erro ao carregar operadores: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao carregar operadores:', error);
        mostrarNotificacao(`Erro ao carregar operadores: ${error.message}`, 'danger');
    } finally {
        if (carregandoOperadores) {
            carregandoOperadores.remove();
            carregandoOperadores = null;
        }
        
        // Verificar se o elemento semOperadores existe antes de tentar acessá-lo
        if (semOperadores) {
            if (dadosOperadores.length === 0) {
                semOperadores.classList.remove('d-none');
            } else {
                semOperadores.classList.add('d-none');
            }
        }
    }
}

// Renderizar tabela de operadores
function renderizarTabelaOperadores() {
    const filtro = filtroOperador.value.toLowerCase();
    const operadoresFiltrados = dadosOperadores.filter(operador => 
        filtro === '' || 
        operador.nome.toLowerCase().includes(filtro) || 
        (operador.descricao && operador.descricao.toLowerCase().includes(filtro))
    );
    
    // Limpar tabela
    const rows = tabelaOperadores.querySelectorAll('tr:not(#carregando-operadores)');
    rows.forEach(row => row.remove());
    
    if (operadoresFiltrados.length === 0) {
        const trVazio = document.createElement('tr');
        trVazio.innerHTML = `
            <td colspan="6" class="text-center py-4">
                <div class="py-5">
                    <i class="bi bi-search text-muted" style="font-size: 2rem;"></i>
                    <p class="mt-3">Nenhum operador encontrado com os critérios de filtro.</p>
                </div>
            </td>
        `;
        tabelaOperadores.appendChild(trVazio);
        
        // Verificar se o elemento semOperadores existe antes de manipulá-lo
        if (semOperadores) {
            semOperadores.classList.add('d-none');
        }
        return;
    }
    
    // Adicionar linhas para cada operador
    operadoresFiltrados.forEach(operador => {
        const tr = document.createElement('tr');
        tr.classList.add('fade-in');
        
        // Status com badge
        const onlineStatus = operador.online ? 
            `<span class="badge status-badge online"><i class="bi bi-plug-fill"></i> Online</span>` : 
            `<span class="badge status-badge offline"><i class="bi bi-plug"></i> Offline</span>`;
        
        // Status detalhado para operadores online
        let statusDetalhado = '';
        if (operador.online && operador.status) {
            let statusClass = '';
            
            if (operador.status.includes('Executando')) {
                statusClass = 'status-running';
            } else if (operador.status.includes('Parado')) {
                statusClass = 'status-stopped';
            } else {
                statusClass = 'status-waiting';
            }
            
            statusDetalhado = `<div class="mt-2"><span class="status-circle ${statusClass}"></span> ${operador.status}</div>`;
        }
        
        // Configurações
        const configs = `
            <div class="config-section">
                <strong>Username</strong>
                <div class="config-value">${escapeHtml(operador.username)}</div>
            </div>
        `;
        
        // Última atualização
        const ultimaAtualizacao = operador.online && operador.ultima_atualizacao ? 
            `<div>${formatarData(operador.ultima_atualizacao)}</div><small class="text-muted">${tempoRelativo(operador.ultima_atualizacao)}</small>` : 
            '<span class="text-muted">-</span>';
        
        // Botões de ação
        const botoes = `
            <div class="action-cell">
                ${operador.online ? `
                    <button class="btn btn-sm btn-success" onclick="enviarComando('${operador.id}', 'iniciar')" title="Iniciar">
                        <i class="bi bi-play-fill"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="enviarComando('${operador.id}', 'parar')" title="Parar">
                        <i class="bi bi-stop-fill"></i>
                    </button>
                    <button class="btn btn-sm btn-warning" onclick="enviarComando('${operador.id}', 'reiniciar')" title="Reiniciar">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                    
                    <div class="action-group">
                        <button class="btn btn-sm btn-primary" onclick="editarOperador('${operador.id}')" title="Editar">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="confirmarExclusao('${operador.id}', '${escapeHtml(operador.nome)}')" title="Excluir">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                ` : `
                    <button class="btn btn-sm btn-light" disabled title="Iniciar">
                        <i class="bi bi-play-fill text-muted"></i>
                    </button>
                    <button class="btn btn-sm btn-light" disabled title="Parar">
                        <i class="bi bi-stop-fill text-muted"></i>
                    </button>
                    <button class="btn btn-sm btn-light" disabled title="Reiniciar">
                        <i class="bi bi-arrow-clockwise text-muted"></i>
                    </button>
                    
                    <div class="action-group">
                        <button class="btn btn-sm btn-primary" onclick="editarOperador('${operador.id}')" title="Editar">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="confirmarExclusao('${operador.id}', '${escapeHtml(operador.nome)}')" title="Excluir">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `}
            </div>
        `;
        
        tr.innerHTML = `
            <td>
                <div class="fw-bold">${escapeHtml(operador.nome)}</div>
            </td>
            <td>${onlineStatus}${statusDetalhado}</td>
            <td>${operador.descricao ? escapeHtml(operador.descricao) : '<span class="text-muted fst-italic">Sem descrição</span>'}</td>
            <td>${configs}</td>
            <td>${ultimaAtualizacao}</td>
            <td class="text-center">${botoes}</td>
        `;
        
        tabelaOperadores.appendChild(tr);
    });
    
    // Verificar se o elemento semOperadores existe antes de manipulá-lo
    if (semOperadores) {
        semOperadores.classList.add('d-none');
    }
}

// Função para abrir modal de edição
async function editarOperador(operadorId) {
    try {
        // Mostrar indicador de carregamento
        const btnEditar = document.querySelector(`button[onclick="editarOperador('${operadorId}')"]`);
        const btnIcon = btnEditar.querySelector('i');
        btnIcon.className = 'spinner-border spinner-border-sm';
        btnEditar.disabled = true;
        
        const response = await fetch(`/api/operadores/${operadorId}`);
        const data = await response.json();
        
        // Restaurar ícone
        btnIcon.className = 'bi bi-pencil';
        btnEditar.disabled = false;
        
        if (data.success) {
            const operador = data.operador;
            
            // Campos básicos com verificação de existência
            const elId = document.getElementById('edit-id');
            const elNome = document.getElementById('edit-nome');
            const elDesc = document.getElementById('edit-descricao');
            const elTipo = document.getElementById('edit-tipo_cadastro');
            
            if (elId) elId.value = operador.id;
            if (elNome) elNome.value = operador.nome;
            if (elDesc) elDesc.value = operador.descricao || '';
            if (elTipo) elTipo.value = operador.tipo_cadastro || 'Monitor de Senhas';
            
            // Credenciais Compartilhadas
            const elUser = document.getElementById('edit-username');
            const elPass = document.getElementById('edit-password');
            if (elUser) elUser.value = operador.username || '';
            if (elPass) elPass.value = operador.password || '';
            
            // Credenciais Separadas e Switch
            const elUsaSeparadas = document.getElementById('edit-usa_credenciais_separadas');
            if (elUsaSeparadas) {
                elUsaSeparadas.checked = !!operador.usa_credenciais_separadas; // Forçar booleano
            }
            
            const elUserMon = document.getElementById('edit-username_monitor');
            const elPassMon = document.getElementById('edit-password_monitor');
            const elUserTot = document.getElementById('edit-username_totem');
            const elPassTot = document.getElementById('edit-password_totem');
            
            if (elUserMon) elUserMon.value = operador.username_monitor || '';
            if (elPassMon) elPassMon.value = operador.password_monitor || '';
            if (elUserTot) elUserTot.value = operador.username_totem || '';
            if (elPassTot) elPassTot.value = operador.password_totem || '';
            
            // Atualizar visibilidade dos campos
            toggleCredenciaisEdicao();
            
            // Verificar se existe o elemento de voz preferida
            const editVozPreferida = document.getElementById('edit-voz_preferida');
            if (editVozPreferida) {
                // Se o elemento existe, carregar as vozes disponíveis
                try {
                    // Buscar vozes disponíveis do sistema
                    const vozesResponse = await fetch('/api/vozes-disponiveis');
                    const vozesData = await vozesResponse.json();
                    
                    // Limpar o select
                    editVozPreferida.innerHTML = '<option value="">Selecione uma voz (ou deixe em branco para usar padrão)</option>';
                    
                    if (vozesData.success && vozesData.vozes && vozesData.vozes.length > 0) {
                        // Adicionar as vozes ao select
                        vozesData.vozes.forEach(voz => {
                            const option = document.createElement('option');
                            option.value = voz.nome;
                            option.textContent = `${voz.nome} (${voz.idioma || 'Sem idioma'}, ${voz.tipo === 'remota/nuvem' ? 'Remota/Nuvem' : 'Local'})`;
                            
                            // Selecionar a voz atual, se existir
                            if (operador.voz_preferida === voz.nome) {
                                option.selected = true;
                            }
                            
                            editVozPreferida.appendChild(option);
                        });
                        
                        // Se a voz atual não estiver na lista mas existir, adicione-a
                        if (operador.voz_preferida && !vozesData.vozes.some(voz => voz.nome === operador.voz_preferida)) {
                            const optionVozAtual = document.createElement('option');
                            optionVozAtual.value = operador.voz_preferida;
                            optionVozAtual.textContent = `${operador.voz_preferida} (voz atual)`;
                            optionVozAtual.selected = true;
                            editVozPreferida.appendChild(optionVozAtual);
                        }
                    } else {
                        // Adicionar um item de "sem vozes disponíveis"
                        const option = document.createElement('option');
                        option.value = "";
                        option.textContent = "Não há vozes disponíveis - Operador precisa estar online para sincronizar";
                        option.disabled = true;
                        editVozPreferida.appendChild(option);
                        
                        // Se tiver uma voz atual, adicioná-la manualmente
                        if (operador.voz_preferida) {
                            const optionVozAtual = document.createElement('option');
                            optionVozAtual.value = operador.voz_preferida;
                            optionVozAtual.textContent = `${operador.voz_preferida} (voz atual)`;
                            optionVozAtual.selected = true;
                            editVozPreferida.appendChild(optionVozAtual);
                        }
                    }
                } catch (error) {
                    console.error('Erro ao carregar vozes:', error);
                    editVozPreferida.innerHTML = '<option value="">Erro ao carregar vozes disponíveis</option>';
                    
                    // Se tiver uma voz atual, adicioná-la manualmente
                    if (operador.voz_preferida) {
                        const optionVozAtual = document.createElement('option');
                        optionVozAtual.value = operador.voz_preferida;
                        optionVozAtual.textContent = `${operador.voz_preferida} (voz atual)`;
                        optionVozAtual.selected = true;
                        editVozPreferida.appendChild(optionVozAtual);
                    }
                }
            }
            
            const modal = new bootstrap.Modal(document.getElementById('modalEditarOperador'));
            modal.show();
        } else {
            mostrarNotificacao(`Erro ao carregar operador: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao carregar dados do operador:', error);
        mostrarNotificacao(`Erro ao carregar dados do operador: ${error.message}`, 'danger');
    }
}

// Função para confirmar exclusão
function confirmarExclusao(operadorId, nome) {
    document.getElementById('nome-operador-exclusao').textContent = nome;
    
    // Configurar o botão de exclusão com onclick direto
    const btnConfirmarExclusao = document.getElementById('btnConfirmarExclusao');
    btnConfirmarExclusao.onclick = function() {
        excluirOperador(operadorId);
    };
    
    const modal = new bootstrap.Modal(document.getElementById('modalConfirmarExclusao'));
    modal.show();
}

// Função para adicionar novo operador
async function adicionarOperador() {
    // Obter dados do formulário
    const nome = document.getElementById('nome').value;
    const descricao = document.getElementById('descricao').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // Validar campos obrigatórios
    if (!nome || !username || !password) {
        mostrarNotificacao('Preencha todos os campos obrigatórios', 'danger');
        return;
    }
    
    try {
        // Mostrar indicador de carregamento
        const btnSalvar = document.getElementById('btnSalvarOperador');
        const originalText = btnSalvar.innerHTML;
        btnSalvar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';
        btnSalvar.disabled = true;
        
        // Enviar requisição para adicionar operador
        const response = await fetch('/api/operadores', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nome,
                descricao,
                username,
                password
            })
        });
        
        const data = await response.json();
        
        // Restaurar botão
        btnSalvar.innerHTML = originalText;
        btnSalvar.disabled = false;
        
        if (data.success) {
            // Fechar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalAdicionarOperador'));
            modal.hide();
            
            // Limpar formulário
            document.getElementById('formAdicionarOperador').reset();
            
            // Recarregar operadores
            mostrarNotificacao('Operador adicionado com sucesso', 'success');
            carregarOperadores();
        } else {
            mostrarNotificacao(`Erro ao adicionar operador: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao adicionar operador:', error);
        mostrarNotificacao(`Erro ao adicionar operador: ${error.message}`, 'danger');
        
        // Restaurar botão em caso de erro
        const btnSalvar = document.getElementById('btnSalvarOperador');
        btnSalvar.innerHTML = '<i class="bi bi-check-circle"></i> Salvar';
        btnSalvar.disabled = false;
    }
}

// Função para atualizar operador existente
async function atualizarOperador() {
    // Obter dados do formulário
    const id = document.getElementById('edit-id') ? document.getElementById('edit-id').value : null;
    const nome = document.getElementById('edit-nome') ? document.getElementById('edit-nome').value : '';
    const descricao = document.getElementById('edit-descricao') ? document.getElementById('edit-descricao').value : '';
    const tipo_cadastro = document.getElementById('edit-tipo_cadastro') ? document.getElementById('edit-tipo_cadastro').value : 'Monitor de Senhas';
    
    // Verificar switch de credenciais separadas
    const elUsaSeparadas = document.getElementById('edit-usa_credenciais_separadas');
    const usa_credenciais_separadas = elUsaSeparadas ? elUsaSeparadas.checked : false;
    
    let username = '', password = '';
    let username_monitor = '', password_monitor = '';
    let username_totem = '', password_totem = '';
    
    if (usa_credenciais_separadas) {
        username_monitor = document.getElementById('edit-username_monitor') ? document.getElementById('edit-username_monitor').value : '';
        password_monitor = document.getElementById('edit-password_monitor') ? document.getElementById('edit-password_monitor').value : '';
        username_totem = document.getElementById('edit-username_totem') ? document.getElementById('edit-username_totem').value : '';
        password_totem = document.getElementById('edit-password_totem') ? document.getElementById('edit-password_totem').value : '';
        
        // Validação para credenciais separadas
        if (!username_monitor || !password_monitor || !username_totem || !password_totem) {
             // Se for tipo "Ambos", precisa de tudo. Se for só Monitor, precisa só de monitor...
             // Simplificação: Se ativou separadas, pedimos tudo por segurança ou validamos conforme tipo
             // Vamos validar o básico: campos não podem ser vazios se forem usados
        }
    } else {
        username = document.getElementById('edit-username') ? document.getElementById('edit-username').value : '';
        password = document.getElementById('edit-password') ? document.getElementById('edit-password').value : '';
    }
    
    // Verificar se existe o elemento de voz preferida
    let voz_preferida = '';
    const editVozPreferida = document.getElementById('edit-voz_preferida');
    if (editVozPreferida) {
        voz_preferida = editVozPreferida.value;
    }
    
    // Validar campos obrigatórios
    if (!nome) {
        mostrarNotificacao('Nome do operador é obrigatório', 'danger');
        return;
    }
    
    if (usa_credenciais_separadas) {
        // Validação mais específica poderia ser feita aqui
        if ((!username_monitor || !password_monitor) && (tipo_cadastro.includes('Monitor') || tipo_cadastro === 'Ambos')) {
             // Aviso opcional, mas vamos deixar passar por enquanto
        }
    } else {
        if (!username || !password) {
            mostrarNotificacao('Usuário e Senha são obrigatórios', 'danger');
            return;
        }
    }
    
    try {
        // Mostrar indicador de carregamento
        const btnAtualizar = document.getElementById('btnAtualizarOperador');
        const originalText = btnAtualizar.innerHTML;
        btnAtualizar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';
        btnAtualizar.disabled = true;
        
        // Enviar requisição para atualizar operador
        const response = await fetch(`/api/operadores/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nome,
                descricao,
                tipo_cadastro,
                usa_credenciais_separadas,
                username,
                password,
                username_monitor,
                password_monitor,
                username_totem,
                password_totem,
                voz_preferida
            })
        });
        
        const data = await response.json();
        
        // Restaurar botão
        btnAtualizar.innerHTML = originalText;
        btnAtualizar.disabled = false;
        
        if (data.success) {
            // Fechar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalEditarOperador'));
            modal.hide();
            
            // Recarregar operadores
            mostrarNotificacao('Operador atualizado com sucesso', 'success');
            carregarOperadores();
        } else {
            mostrarNotificacao(`Erro ao atualizar operador: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao atualizar operador:', error);
        mostrarNotificacao(`Erro ao atualizar operador: ${error.message}`, 'danger');
        
        // Restaurar botão em caso de erro
        const btnAtualizar = document.getElementById('btnAtualizarOperador');
        btnAtualizar.innerHTML = 'Salvar Alterações';
        btnAtualizar.disabled = false;
    }
}

// Função para excluir operador
async function excluirOperador(operadorId) {
    if (!operadorId) {
        console.error('ID do operador não fornecido para exclusão');
        mostrarNotificacao('Erro: ID do operador não fornecido', 'danger');
        return;
    }
    
    try {
        // Mostrar indicador de carregamento
        const btnExcluir = document.getElementById('btnConfirmarExclusao');
        const originalText = btnExcluir.innerHTML;
        btnExcluir.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Excluindo...';
        btnExcluir.disabled = true;
        
        const response = await fetch(`/api/operadores/${operadorId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        // Restaurar botão
        btnExcluir.innerHTML = originalText;
        btnExcluir.disabled = false;
        
        if (data.success) {
            // Fechar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalConfirmarExclusao'));
            modal.hide();
            
            // Remover operador da lista local e atualizar tabela
            dadosOperadores = dadosOperadores.filter(op => op.id !== operadorId);
            renderizarTabelaOperadores();
            
            if (dadosOperadores.length === 0) {
                semOperadores.classList.remove('d-none');
            }
            
            mostrarNotificacao('Operador excluído com sucesso', 'success');
        } else {
            mostrarNotificacao(`Erro ao excluir operador: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erro ao excluir operador:', error);
        mostrarNotificacao(`Erro ao excluir operador: ${error.message}`, 'danger');
        
        // Restaurar botão em caso de erro
        const btnExcluir = document.getElementById('btnConfirmarExclusao');
        btnExcluir.innerHTML = 'Excluir Permanentemente';
        btnExcluir.disabled = false;
    }
} 