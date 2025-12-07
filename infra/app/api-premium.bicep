param name string
@description('Primary location for all resources')
param location string = resourceGroup().location
param tags object = {}
param applicationInsightsName string = ''
param appServicePlanId string
param appSettings object = {}
param runtimeName string 
param runtimeVersion string 
param serviceName string = 'api'
param storageAccountName string
param virtualNetworkSubnetId string = ''
param identityId string = ''
param identityClientId string = ''
param enableBlob bool = true
param enableQueue bool = true
param enableTable bool = false
param enableFile bool = true

@allowed(['SystemAssigned', 'UserAssigned'])
param identityType string = 'UserAssigned'

var applicationInsightsIdentity = 'ClientId=${identityClientId};Authorization=AAD'
var kind = 'functionapp,linux'

// Create base application settings for Premium plan using Managed Identity
var baseAppSettings = {
  // Managed Identity for storage access (no shared keys needed)
  AzureWebJobsStorage__accountName: storageAccountName
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__clientId: identityClientId
  
  // Application Insights settings
  APPLICATIONINSIGHTS_AUTHENTICATION_STRING: applicationInsightsIdentity
  APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights.properties.ConnectionString
  
  // Function runtime settings
  FUNCTIONS_EXTENSION_VERSION: '~4'
  FUNCTIONS_WORKER_RUNTIME: runtimeName
  
  // Deployment settings for Python on Premium plan
  WEBSITE_RUN_FROM_PACKAGE: '0'
  SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
  ENABLE_ORYX_BUILD: 'true'
  
  // Python specific settings
  PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
  BUILD_FLAGS: 'UseExpressBuild'
  XDG_CACHE_HOME: '/tmp/.cache'
}

// Dynamically build storage endpoint settings based on feature flags
var blobSettings = enableBlob ? { AzureWebJobsStorage__blobServiceUri: stg.properties.primaryEndpoints.blob } : {}
var queueSettings = enableQueue ? { AzureWebJobsStorage__queueServiceUri: stg.properties.primaryEndpoints.queue } : {}
var tableSettings = enableTable ? { AzureWebJobsStorage__tableServiceUri: stg.properties.primaryEndpoints.table } : {}
var fileSettings = enableFile ? { AzureWebJobsStorage__fileServiceUri: stg.properties.primaryEndpoints.file } : {}

// Merge all app settings
var allAppSettings = union(
  appSettings,
  blobSettings,
  queueSettings,
  tableSettings,
  fileSettings,
  baseAppSettings
)

resource stg 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightsName)) {
  name: applicationInsightsName
}

// Create a Premium Function App to host the API
module api 'br/public:avm/res/web/site:0.15.1' = {
  name: '${serviceName}-premium'
  params: {
    kind: kind
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    serverFarmResourceId: appServicePlanId
    managedIdentities: {
      systemAssigned: identityType == 'SystemAssigned'
      userAssignedResourceIds: [
        '${identityId}'
      ]
    }
    siteConfig: {
      alwaysOn: true
      linuxFxVersion: 'PYTHON|${runtimeVersion}'
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
          'http://localhost:5173'
          'http://127.0.0.1:5173'
          '*'
        ]
        supportCredentials: false
      }
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
    virtualNetworkSubnetId: !empty(virtualNetworkSubnetId) ? virtualNetworkSubnetId : null
    appSettingsKeyValuePairs: allAppSettings
  }
}

output SERVICE_API_NAME string = api.outputs.name
output SERVICE_API_IDENTITY_PRINCIPAL_ID string = identityType == 'SystemAssigned' ? api.outputs.?systemAssignedMIPrincipalId ?? '' : ''
