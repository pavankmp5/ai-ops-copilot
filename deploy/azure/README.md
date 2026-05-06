# Azure Container Apps Deployment

Azure Container Apps remains the recommended host for this project. With the Postgres-ready backend and Azure Blob-ready dataset storage abstraction in place, the deployment path is now much closer to a real scalable production shape.

Official references:

- Azure Container Apps quickstart: https://learn.microsoft.com/en-us/azure/container-apps/quickstart-portal
- Azure Container Apps from source with `az containerapp up`: https://learn.microsoft.com/en-us/azure/container-apps/containerapp-up
- Azure Container Apps environment variables: https://learn.microsoft.com/en-us/azure/container-apps/environment-variables
- Azure Container Apps secrets: https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets
- Azure Container Apps health probes: https://learn.microsoft.com/en-us/azure/container-apps/health-probes
- Azure Database for PostgreSQL Flexible Server: https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview
- Azure Storage account overview: https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview

## GitHub Actions Deployment Inputs

If you use `.github/workflows/deploy-azure.yml`, configure these repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINERAPPS_ENV`
- `AZURE_BACKEND_APP_NAME`
- `AZURE_FRONTEND_APP_NAME`
- `JWT_SECRET_KEY`
- `OPENROUTER_API_KEY`
- `DATABASE_URL`
- `AZURE_BLOB_CONNECTION_STRING`
- `AZURE_BLOB_CONTAINER`

## Recommended Azure Topology

- `ai-ops-backend`: FastAPI Azure Container App
- `ai-ops-frontend`: React/Nginx Azure Container App
- Azure Database for PostgreSQL Flexible Server
- Azure Storage Account with Blob container for datasets

This is the strongest practical Azure path for this project because it gives you:

- containerized deployment for frontend and backend
- managed Postgres for scalable relational state
- Blob storage for uploaded datasets
- health probes, ingress, revisions, and runtime config via Container Apps

## Environment Variables

Backend:

- `ENVIRONMENT=production`
- `LOG_JSON=true`
- `JWT_SECRET_KEY=<secure secret>`
- `OPENROUTER_API_KEY=<provider key>`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `LLM_MODEL=openai/gpt-4o-mini`
- `DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<db>?sslmode=require`
- `STORAGE_PROVIDER=azure_blob`
- `AZURE_BLOB_CONNECTION_STRING=<connection string>`
- `AZURE_BLOB_CONTAINER=ai-ops-datasets`
- `CORS_ALLOWED_ORIGINS=https://<frontend-fqdn>`

Frontend:

- `API_BASE_URL=https://<backend-fqdn>`
- `DOCS_URL=https://<backend-fqdn>/docs`

## ACA Health Probes

Backend target port: `8000`

- Startup: `GET /health`
- Liveness: `GET /health`
- Readiness: `GET /readyz`

Frontend target port: `80`

- Startup: `GET /`
- Liveness: `GET /`
- Readiness: `GET /`

## Tightened Azure CLI Flow

### 1. Prerequisites

```powershell
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.Storage
```

### 2. Set names

```powershell
$RG="aiops-prod-rg"
$LOC="centralindia"
$ENV="aiops-container-env"
$BACKEND="aiops-backend"
$FRONTEND="aiops-frontend"
$STORAGE="aiopsstorage$(Get-Random -Maximum 9999)"
$POSTGRES="aiops-postgres-flex"
$DBUSER="aiopsadmin"
$DBPASS="ReplaceThisWithAStrongPassword123!"
$DBNAME="aiops"
```

### 3. Create resource group

```powershell
az group create --name $RG --location $LOC
```

### 4. Create storage account and blob container

```powershell
az storage account create `
  --name $STORAGE `
  --resource-group $RG `
  --location $LOC `
  --sku Standard_LRS `
  --kind StorageV2
```

```powershell
$STORAGE_KEY = az storage account keys list `
  --resource-group $RG `
  --account-name $STORAGE `
  --query "[0].value" -o tsv
```

```powershell
az storage container create `
  --name ai-ops-datasets `
  --account-name $STORAGE `
  --account-key $STORAGE_KEY
```

```powershell
$BLOB_CONNECTION = "DefaultEndpointsProtocol=https;AccountName=$STORAGE;AccountKey=$STORAGE_KEY;EndpointSuffix=core.windows.net"
```

### 5. Create PostgreSQL Flexible Server

```powershell
az postgres flexible-server create `
  --name $POSTGRES `
  --resource-group $RG `
  --location $LOC `
  --admin-user $DBUSER `
  --admin-password $DBPASS `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --version 16 `
  --storage-size 32
```

```powershell
az postgres flexible-server db create `
  --resource-group $RG `
  --server-name $POSTGRES `
  --database-name $DBNAME
```

```powershell
$DBHOST = az postgres flexible-server show `
  --resource-group $RG `
  --name $POSTGRES `
  --query fullyQualifiedDomainName -o tsv
```

```powershell
$DATABASE_URL = "postgresql://$DBUSER:$DBPASS@$DBHOST:5432/$DBNAME?sslmode=require"
```

### 6. Create Container Apps environment

```powershell
az containerapp env create `
  --name $ENV `
  --resource-group $RG `
  --location $LOC
```

### 7. Deploy backend from source

Run from the repo root:

```powershell
cd f:\Python_learning\ai_ops_copilot

az containerapp up `
  --name $BACKEND `
  --resource-group $RG `
  --environment $ENV `
  --source . `
  --ingress external `
  --target-port 8000
```

### 8. Set backend secrets

```powershell
az containerapp secret set `
  --name $BACKEND `
  --resource-group $RG `
  --secrets `
    jwt-secret-key="replace-with-a-real-jwt-secret" `
    openrouter-api-key="replace-with-provider-key" `
    database-url="$DATABASE_URL" `
    blob-connection="$BLOB_CONNECTION"
```

### 9. Configure backend env vars

```powershell
az containerapp update `
  --name $BACKEND `
  --resource-group $RG `
  --min-replicas 1 `
  --max-replicas 3 `
  --set-env-vars `
    ENVIRONMENT=production `
    LOG_JSON=true `
    DOCS_ENABLED=true `
    JWT_SECRET_KEY=secretref:jwt-secret-key `
    OPENROUTER_API_KEY=secretref:openrouter-api-key `
    DATABASE_URL=secretref:database-url `
    STORAGE_PROVIDER=azure_blob `
    AZURE_BLOB_CONNECTION_STRING=secretref:blob-connection `
    AZURE_BLOB_CONTAINER=ai-ops-datasets `
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1 `
    LLM_MODEL=openai/gpt-4o-mini
```

### 10. Get backend URL

```powershell
$BACKEND_FQDN = az containerapp show `
  --name $BACKEND `
  --resource-group $RG `
  --query properties.configuration.ingress.fqdn -o tsv
```

### 11. Deploy frontend from source

Run from `frontend/`:

```powershell
cd f:\Python_learning\ai_ops_copilot\frontend

az containerapp up `
  --name $FRONTEND `
  --resource-group $RG `
  --environment $ENV `
  --source . `
  --ingress external `
  --target-port 80
```

### 12. Configure frontend runtime env

```powershell
az containerapp update `
  --name $FRONTEND `
  --resource-group $RG `
  --min-replicas 1 `
  --max-replicas 3 `
  --set-env-vars `
    API_BASE_URL=https://$BACKEND_FQDN `
    DOCS_URL=https://$BACKEND_FQDN/docs
```

### 13. Update backend CORS

```powershell
$FRONTEND_FQDN = az containerapp show `
  --name $FRONTEND `
  --resource-group $RG `
  --query properties.configuration.ingress.fqdn -o tsv
```

```powershell
az containerapp update `
  --name $BACKEND `
  --resource-group $RG `
  --set-env-vars `
    CORS_ALLOWED_ORIGINS=https://$FRONTEND_FQDN
```

### 14. Validate deployment

Check:

- `https://<backend-fqdn>/health`
- `https://<backend-fqdn>/readyz`
- `https://<backend-fqdn>/system/status`
- frontend login
- frontend upload
- dataset question
- general question

## Scaling Guidance

- Frontend: safe to scale horizontally
- Backend: now better prepared for scaling because DB and dataset storage can move to managed services
- RAG store: Chroma is still local to the container unless you replace it with a shared vector store later

That means the biggest remaining scale constraint after this pass is vector storage, not auth/data metadata.

## Troubleshooting `10054` (connection reset)

On Windows, `10054` typically means "connection reset by peer." In this stack, the most common causes are:

- container revision fails startup and ingress closes/reset connections
- backend cannot reach PostgreSQL (bad host/firewall/SSL) and never becomes ready
- intermittent control-plane/network errors during `az containerapp up`

Useful checks:

```powershell
az containerapp revision list --name <backend-app> --resource-group <rg> -o table
az containerapp logs show --name <backend-app> --resource-group <rg> --tail 200
az containerapp show --name <backend-app> --resource-group <rg> --query properties.latestRevisionName -o tsv
```

If deployment intermittently fails with reset/transport errors, rerun deploy after a short delay. The workflow includes retry loops for `az containerapp up` to reduce these transient failures.
