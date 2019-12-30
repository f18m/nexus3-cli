from nexuscli.api.repository.collection import AssetMatchOptions


# unit test for repository.delete_assets()
def test_delete(faker, nexus_mock_client, mocker):
    """
    Given a repository_path and a response from the service, ensure that the
    method deletes the expected artefacts.
    """
    nexus = nexus_mock_client
    x_repository = faker.uri_path()
    x_count = faker.random_int(20, 100)

    # list with random count of artefact paths without the leading /
    x_artefacts = [
        faker.file_path(
            depth=faker.random_int(2, 10))[1:] for _ in range(x_count)
    ]

    # patch the function that should run the Groovy script:
    nexus.scripts.run = mocker.Mock(return_value={
      'name': 'nexus3-cli-repository-delete-assets',
      'result': '{"success":true,"error":"","assets":["/reponame/assetname"]}'
    })

    matchMode = AssetMatchOptions.EXACT_NAME
    for artifact in x_artefacts:
        # call actual method being tested
        deleted = nexus.repositories.delete_assets(x_repository, artifact,
                                                   matchMode, False)
        delete_count = len(deleted)
        assert delete_count == 1

    nexus.scripts.run.assert_called()
