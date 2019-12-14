// Original from:
// https://github.com/hlavki/nexus-scripts
// Modified to include some improvements to 
//  - logging
//  - option to do a "dry run"
//  - support for EXACT_NAME, WILDCARD or REGEX matching methods

import org.sonatype.nexus.repository.storage.Asset
import org.sonatype.nexus.repository.storage.Query
import org.sonatype.nexus.repository.storage.StorageFacet
import org.sonatype.nexus.repository.raw.internal.RawFormat

import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def log_prefix = "nexus3-cli GROOVY SCRIPT: "

// https://gist.github.com/kellyrob99/2d1483828c5de0e41732327ded3ab224
// https://gist.github.com/emexelem/bcf6b504d81ea9019ad4ab2369006e66

def request = new JsonSlurper().parseText(args)
assert request.repoName: 'repoName parameter is required'
assert request.assetName: 'name regular expression parameter is required, format: regexp'
assert request.assetMatchType != null: 'assetMatchType parameter is required'
assert request.assetMatchType == 'EXACT_NAME' || request.assetMatchType == 'WILDCARD' || request.assetMatchType == 'REGEX': 'assetMatchType parameter value is invalid: ${request.assetName}'
assert request.dryRun != null: 'dryRun parameter is required'

def repo = repository.repositoryManager.get(request.repoName)
if (repo == null) {
    log.warn(log_prefix +  "Repository ${request.repoName} does not exist")

    def result = JsonOutput.toJson([
        success   : false,
        error     : "Repository '${request.repoName}' does not exist.",
        assets    : null
    ])
    return result
}
else if (repo.type != 'hosted') {
    log.warn(log_prefix +  "Repository ${request.repoName} has type ${repo.type}; only HOSTED repositories are supported for delete operations.")

    def result = JsonOutput.toJson([
        success   : false,
        error     : "Repository '${request.repoName}' has invalid type '${repo.type}'; expecting an HOSTED repository.",
        assets    : null
    ])
    return result
}

log.info(log_prefix + "Valid repository: ${request.repoName}, of type: ${repo.type} and format: ${repo.format}")

StorageFacet storageFacet = repo.facet(StorageFacet)
def tx = storageFacet.txSupplier().get()

try {
    tx.begin()

    log.info(log_prefix + "Gathering list of assets from repository: ${request.repoName} matching pattern: ${request.assetName}  assetMatchType: ${request.assetMatchType}")
    Iterable<Asset> assets
    if (request.assetMatchType == 'EXACT_NAME')
        assets = tx.findAssets(Query.builder().where('name = ').param(request.assetName).build(), [repo])
    else if (request.assetMatchType == 'WILDCARD')
        assets = tx.findAssets(Query.builder().where('name like ').param(request.assetName).build(), [repo])
    else if (request.assetMatchType == 'REGEX')
        assets = tx.findAssets(Query.builder().where('name MATCHES ').param(request.assetName).build(), [repo])
    else
        assert false: 'we should never get here'

    def urls = assets.collect { "/${repo.name}/${it.name()}" }

    if (request.dryRun == false) {
        // add in the transaction a delete command for each asset
        assets.each { asset ->
            log.info(log_prefix + "Deleting asset ${asset.name()}")
            tx.deleteAsset(asset);

            def assetId = asset.componentId()
            if (assetId != null) {
                def component = tx.findComponent(assetId);
                if (component != null) {
                    log.info(log_prefix + "Deleting component with ID ${assetId} that belongs to asset ${asset.name()}")
                    tx.deleteComponent(component);
                }
            }
        }
    }

    tx.commit()
    log.info(log_prefix + "Transaction committed successfully")

    def result = JsonOutput.toJson([
        success   : true,
        error     : "",
        assets    : urls
    ])
    return result

} catch (all) {
    log.warn(log_prefix + "Exception: ${all}")
    all.printStackTrace()
    log.info(log_prefix + "Rolling back changes...")
    tx.rollback()
    log.info(log_prefix + "Rollback done.")

    def result = JsonOutput.toJson([
        success   : false,
        error     : "Exception during processing.",
        assets    : null
    ])
    return result

} finally {
    // @todo Fix me! Danger Will Robinson!
    tx.close()
}
