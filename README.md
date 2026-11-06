# LuzViva: infra e deploy (Secure DevOps & Cloud)

> Esta pasta traz a parte do **Matheus (DevOps)**. O app real é o do Caíque (`luzviva-app`):
> copie `Dockerfile`, `docker-compose.yml`, `infra/`, `monitoring/` e `.github/` para o repositório
> dele. A pasta `app/` aqui é só um **placeholder** para testar a infra. Contrato que o app precisa
> cumprir: `GET /health` e `GET /metrics` (com `http_requests_total` e `http_request_duration_seconds`).

## Ficha Técnica
(Cole aqui a Ficha Técnica da skill `gs-luzviva-projeto` e preencha a URL: `http://<app_ip>`.)
Integrantes (nome completo e RM dos cinco) também abrem este README.

## Arquitetura
```
push/PR → GitHub Actions: testes → Gitleaks → Semgrep → build → Trivy
                                                          │ (só main)
                                                          ▼
                                                  GHCR (imagem pública)
                                                          │  SSM Run Command (sem porta 22)
                                                          ▼
Internet ──HTTP 80──► EC2 (Elastic IP) ── Docker: app FastAPI :8000
                                              ▲ /metrics
        Prometheus + Grafana (local, na sua máquina) ┘
```

## 1. Rodar local
```bash
cp .env.example .env        # defina GRAFANA_PASSWORD
docker compose up --build
# app: http://localhost:8000/health | Prometheus: :9090 | Grafana: :3000 (usuário admin)
```
O dashboard "LuzViva: 4 métricas de ouro" já vem provisionado.

## 2. Subir a infra (Learner Lab)
1. Inicie o lab e copie **AWS Details → AWS CLI** (access key, secret e session token) para `~/.aws/credentials`.
2. `cd infra && cp terraform.tfvars.example terraform.tfvars` e ajuste `image`.
3. `terraform init && terraform plan && terraform apply`
4. Guarde os outputs `app_ip`, `app_url` e `instance_id`.
5. Confirme o SSM: `aws ssm describe-instance-information` deve listar a instância (pode levar alguns minutos).

## 3. Configurar o GitHub
- **Secrets:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `INSTANCE_ID`.
- **Variables:** `AWS_REGION` (ex.: `us-east-1`), `APP_URL` (`http://<app_ip>`).
- **Learner Lab:** as 3 credenciais expiram quando a sessão acaba. Antes de cada deploy, reinicie o lab e atualize os 3 secrets.
- Depois do primeiro push na `main`, torne o pacote do GHCR **público** (Perfil → Packages → pacote → Package settings → Change visibility). Sem isso a EC2 não consegue baixar a imagem.
- Recomendado: proteger a `main` (ruleset exigindo o check `ci-ok`).

## 4. Evidências para o PDF (14 pontos)
| Bloco | Print / prova |
|---|---|
| Docker (2,0) | `docker compose up` rodando; `docker run --rm IMAGE id` mostrando usuário não root |
| Terraform (3,0) | `terraform apply` concluído; Security Group só com porta 80; `.gitignore` com state e tfvars |
| Pipeline (4,0) | Run **vermelho** (segredo falso) e run **verde** (corrigido); jobs Gitleaks, Semgrep e Trivy |
| Observabilidade (3,0) | Dashboard com as 4 métricas; alerta `TaxaDeErros5xxAlta` em **Firing** (Prometheus → Alerts) |
| Documentação (2,0) | Diagrama acima, responsabilidade compartilhada, LGPD, custo, este README |

**Run barrado:** em uma branch de teste, commite um arquivo com um segredo falso no formato de chave AWS e faça push. O Gitleaks varre os commits do push, então depois de dar `git revert` e push de novo o run fica verde. Teste antes se o padrão que você usou dispara a regra (alguns exemplos conhecidos são ignorados). Em segredo real, apagar não basta: é preciso revogar.

**Alerta disparado:** `PROM_CONFIG=prometheus.remote.yml` (troque o IP no arquivo), `docker compose up`, depois gere erros: `for i in $(seq 1 200); do curl -s http://<app_ip>/erro > /dev/null; sleep 0.5; done`. Em Prometheus → Alerts, a regra passa a Pending e depois Firing.

## 5. LGPD
Dados pessoais do sistema: fotos do cidadão (rosto, placa de carro, local) e contato opcional. Ficam só no app, nunca no repositório nem no pipeline. A região padrão do Learner Lab é os EUA (`us-east-1`), então registre no PDF que há transferência internacional e que o placeholder não guarda dado pessoal. `/metrics` expõe só contadores técnicos, sem dado pessoal.

## 6. Custo
Estimar na AWS Pricing Calculator: 1 EC2 (tipo da variável `instance_type`) + volume de 12 GB + Elastic IP. O Learner Lab tem orçamento de créditos limitado: acompanhe o saldo no painel do lab. **Não destrua a infra até o fim da correção** (até uma semana após 19/11) e mantenha a instância e o lab ativos nesse período.

## Limitações conhecidas
- Placeholder, Terraform, workflow e compose foram escritos e os testes Python passaram, mas o `terraform validate`, o Docker e o workflow **ainda não foram executados**. Rode e ajuste.
- HTTP na porta 80, sem HTTPS (não há domínio). Se o grupo tiver domínio, adicione TLS.
- `ENABLE_FAULT_ENDPOINT=true` mantém `/erro` ativo para a demo do alerta. Desligue quando não precisar.
