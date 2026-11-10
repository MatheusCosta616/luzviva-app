# LuzViva: MVP no ar com Secure DevOps & Cloud

Global Solution FIAP 2026.2 (CitizenTech), entrega de **Secure DevOps Tools & Cloud Computing**.

| Integrante | RM |
|---|---|
| Caíque Walter Silva | RM550693 |
| Matheus José de Lima Costa | RM551157 |
| João Paulo Fonseca Zamperlini | RM99279 |
| Guilherme Monteiro Espim | RM99499 |
| Guilherme Nobre Bernardo | RM98604 |

## Ficha Técnica do MVP

| Campo | Conteúdo |
|---|---|
| Nome do produto | LuzViva (provisório) |
| Cidadão e território | Pessoas que circulam à noite nas áreas-piloto Sé, Pinheiros e Campo Limpo, em São Paulo |
| Problema, em uma frase | A cidade só descobre que uma luminária apagou quando alguém reclama; até lá, a rua fica escura e insegura |
| Proposta de valor | Encontrar a falha antes da reclamação e dizer ao gestor o que consertar primeiro, com evidência de duas fontes |
| Arquitetura | App FastAPI em container numa EC2 criada por Terraform; pipeline GitHub Actions com Gitleaks, Semgrep e Trivy; Prometheus e Grafana |
| Fontes de dados | Neste MVP: dados simulados no formato dos contratos do grupo (`scripts/gerar_dados.py`). No produto: cadastro ILUME/GeoSampa, SP156, Open-Meteo, medições do robô, ocorrências do app e chamados do RPA |
| Modelos de IA | No produto: YOLO11 (visão), LLM local com RAG (assistente), TinyML no ESP32. Neste MVP o assistente roda em modo simulado: responde citando a fila ou diz "não consta" |
| URL do MVP | http://52.67.217.30 (AWS sa-east-1, São Paulo) |
| Repositório | https://github.com/MatheusCosta616/luzviva-app |
| Indicadores de impacto | % de falhas achadas antes de relato; tempo até o reparo; horas-luminária no escuro por noite |
| ODS | 11 (meta 11.7), 9 e 10 |

## O que o MVP faz
- **Mapa** das luminárias monitoradas, coloridas por situação (acesa, insuficiente, apagada).
- **Fila de manutenção** por prioridade, com botão para abrir chamado.
- **Painel** por subprefeitura (% com falha, horas-luminária no escuro).
- **Chamados**: abrir e atualizar status; nunca dois chamados abertos para a mesma placa.
- **Reportar**: o cidadão informa a placa do poste e o problema, sem nome, e-mail ou telefone.
- **Assistente** do gestor: explica a posição na fila citando a fonte, ou responde "não consta".
- **API** com as rotas do roteiro do grupo (documentação interativa em `/docs`), `/health` e `/metrics`.

**Dados simulados:** nenhum dado aberto informa quais luminárias estão apagadas. `scripts/gerar_dados.py` gera 48 luminárias fictícias (16 por área-piloto) com semente fixa, usando os limiares do contrato (abaixo de 1 lux: apagada; abaixo de 5: insuficiente) e uma regra de prioridade explícita no próprio script. Para regenerar: `python scripts/gerar_dados.py`.

## Arquitetura
```
push/PR ─► GitHub Actions: testes → Gitleaks → Semgrep → build → Trivy ─► ci-ok
                                                       │ (só na main)
                                                       ▼
                                       GHCR: ghcr.io/matheuscosta616/luzviva-app:latest
                                                       ▲  pull a cada 60 s (systemd timer)
Internet ──HTTP 80──► EC2 t3.micro (Elastic IP, SG só porta 80, IMDSv2, disco cifrado)
                        └─ Docker: app FastAPI :8000 (usuário não root) + /opt/luzviva/data
                                       ▲ /metrics
        Prometheus + Grafana (local, apontando para o MVP publicado)
```
**Deploy por pull, sem chave da AWS no GitHub.** No push na `main`, o pipeline publica a imagem no GHCR com o token efêmero `GITHUB_TOKEN`. A EC2 confere a imagem a cada minuto e troca o container quando ela muda. O job `deploy` confirma o deploy lendo `GET /health`, que devolve o commit em execução. Motivo: as credenciais do AWS Academy Learner Lab expiram a cada sessão, e guardá-las no GitHub exigiria recadastrar a cada deploy. Assim não existe credencial de nuvem de longa duração fora da AWS. A EC2 usa o perfil `LabInstanceProfile` já existente.

## 1. Rodar local
```bash
cp .env.example .env        # defina GRAFANA_PASSWORD
docker compose up --build
# app: http://localhost:8000/health | site: http://localhost:8000 | Prometheus: :9090 | Grafana: :3000 (usuário admin)
```
O dashboard "LuzViva: 4 métricas de ouro" já vem provisionado.

## 2. Subir a infra (Learner Lab)
1. Inicie o lab (**Start Lab**) e abra o console da AWS.
2. Rode o Terraform da pasta `infra/` com as credenciais do lab (na sua máquina, com `~/.aws/credentials`, ou no AWS CloudShell):
   ```bash
   cd infra
   cp terraform.tfvars.example terraform.tfvars   # image = "ghcr.io/matheuscosta616/luzviva-app:latest"
   terraform init && terraform plan && terraform apply
   ```
3. Guarde os outputs `app_url` e `instance_id`. `terraform.tfstate` e `terraform.tfvars` ficam fora do Git (`.gitignore`).

## 3. Configurar o GitHub
- **Variable** (Settings → Secrets and variables → Actions → Variables): `APP_URL` = `http://<app_ip>`.
- **Environment** `production` (Settings → Environments), usado pelo job `deploy`.
- **Secrets:** `DEPLOY_TOKEN`, gerado pelo Terraform (`terraform output -raw deploy_token`) e guardado cifrado no SSM Parameter Store. O job `deploy` usa esse token para consultar `/internal/deploy` e confirmar o commit no ar. O `GITHUB_TOKEN` efêmero publica a imagem no GHCR. Nenhuma chave da AWS é cadastrada no GitHub.
- O pacote no GHCR precisa ser **público** (Perfil → Packages → luzviva-app → Package settings → Change visibility) para a EC2 baixar sem credencial.
- Recomendado: ruleset na `main` exigindo o check `ci-ok`.

**Learner Lab:** quando a sessão do lab termina, a AWS para a instância, e ela volta no próximo **Start Lab** com o mesmo Elastic IP. Para a URL ficar no ar durante a correção, inicie o lab antes de entregar e nos dias de correção.

## 4. Evidências para o PDF (14 pontos)
| Bloco | Print / prova |
|---|---|
| Docker (2,0) | `docker compose up` rodando; `docker run --rm IMAGE id` mostrando usuário não root |
| Terraform (3,0) | `terraform apply` concluído; Security Group só com porta 80; `.gitignore` com state e tfvars |
| Pipeline (4,0) | Run **vermelho** (segredo falso) e run **verde** (corrigido); jobs Gitleaks, Semgrep e Trivy |
| Observabilidade (3,0) | Dashboard com as 4 métricas; alerta `TaxaDeErros5xxAlta` em **Firing** (Prometheus → Alerts) |
| Documentação (2,0) | Diagrama acima, responsabilidade compartilhada, LGPD, custo, este README |

**Run barrado:** em uma branch de teste, commite um arquivo com um segredo falso no formato de chave AWS e faça push.  Teste antes se o padrão que você usou dispara a regra (alguns exemplos conhecidos são ignorados). Em segredo real, apagar não basta: é preciso revogar.

**Alerta disparado:** `PROM_CONFIG=prometheus.remote.yml` (troque o IP no arquivo), `docker compose up`, depois gere erros: `for i in $(seq 1 200); do curl -s http://<app_ip>/erro > /dev/null; sleep 0.5; done`. Em Prometheus → Alerts, a regra passa a Pending e depois Firing.

## 5. LGPD
Dados pessoais do sistema: fotos do cidadão (rosto, placa de carro, local) e contato opcional. Ficam só no app, nunca no repositório nem no pipeline. A região padrão do Learner Lab é os EUA (`us-east-1`), então registre no PDF que há transferência internacional e que o placeholder não guarda dado pessoal. `/metrics` expõe só contadores técnicos, sem dado pessoal.

## 6. Custo
Estimar na AWS Pricing Calculator: 1 EC2 (tipo da variável `instance_type`) + volume de 12 GB + Elastic IP. O Learner Lab tem orçamento de créditos limitado: acompanhe o saldo no painel do lab. **Não destrua a infra até o fim da correção** (até uma semana após 19/11) e mantenha a instância e o lab ativos nesse período.

## Dados do app no servidor
Relatos, medições e chamados ficam em `/opt/luzviva/data` na EC2 (montado como `/data` no container, variável `LUZVIVA_DATA_DIR`), então sobrevivem a cada deploy. Um arquivo por fonte e por dia, baixado pelo pipeline de dados em `GET /api/export/<fonte>?data=AAAA-MM-DD`. Variáveis sensíveis do app ficariam em `/opt/luzviva/app.env` na EC2, nunca no repositório. O disco é criptografado e não há backup automático.

## Limitações conhecidas
- Dados simulados; robô, visão, RPA e LLM não estão integrados nesta entrega.
- Rotas de escrita (`POST`/`PATCH`) não têm autenticação. Em produção: token por integração e limite de requisições.
- HTTP na porta 80, sem HTTPS (não há domínio).
- `ENABLE_FAULT_ENDPOINT=true` mantém `/erro` ativo só para a demonstração do alerta.
- Mapa usa Leaflet e tiles do OpenStreetMap carregados da internet.
