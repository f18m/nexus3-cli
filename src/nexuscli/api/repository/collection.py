import json

from nexuscli import exception, nexus_util
from nexuscli.api.repository import model

SCRIPT_NAME_CREATE = 'nexus3-cli-repository-create'
SCRIPT_NAME_DELETE = 'nexus3-cli-repository-delete'
SCRIPT_NAME_DELETE_ASSETS = 'nexus3-cli-repository-delete-assets'


def get_repository_class(raw_repo):
    """

    :param raw_repo:
    :return:
    :rtype: type
    """
    class_name = raw_repo_to_class_name(raw_repo)
    for class_ in model.__all__:
        if class_.__name__ == class_name:
            return class_
    raise NotImplementedError(f'{class_name} for {raw_repo}')


def raw_repo_to_recipe(raw_repo):
    recipe = raw_repo['format']

    if recipe == 'maven2':
        return 'maven'

    return recipe


def raw_repo_to_class_name(raw_repo):
    recipe = raw_repo_to_recipe(raw_repo)
    class_name = ''

    # The Repository class is the default because it implements most of the
    # recipes
    if recipe not in model.Repository.RECIPES:
        class_name += recipe.title()

    class_name += raw_repo['type'].title()

    class_name += 'Repository'

    return class_name


def raw_repo_to_args_kwargs(raw_repo):
    args = (raw_repo['name'],)
    kwargs = {'recipe': raw_repo_to_recipe(raw_repo)}

    if raw_repo['type'] == 'proxy':
        kwargs['remote_url'] = raw_repo['url']

    return args, kwargs


class RepositoryCollection:
    """
    A class to manage Nexus 3 repositories.

    Args:
        client(nexuscli.nexus_client.NexusClient): the client instance that
            will be used to perform operations against the Nexus 3 service. You
            must provide this at instantiation or set it before calling any
            methods that require connectivity to Nexus.
    """
    def __init__(self, client=None):
        self._client = client
        self._repositories_json = None

    def get_by_name(self, name):
        """
        Get a Nexus 3 repository by its name.

        :param name: name of the repository wanted
        :type name: str
        :rtype: nexuscli.api.repository.model.Repository
        :raise exception.NexusClientInvalidRepository: when a repository with
            the given name isn't found.
        """
        try:
            raw_repo = self.get_raw_by_name(name)
        except IndexError:
            raise exception.NexusClientInvalidRepository(name)

        Repository = get_repository_class(raw_repo)
        # FIXME: use groovy to fetch a matching json object so the conversion
        #   isn't required
        args, kwargs = raw_repo_to_args_kwargs(raw_repo)

        return Repository(*args, nexus_client=self._client, **kwargs)

    def get_raw_by_name(self, name):
        """
        Return the raw dict for the repository called ``name``. Remember to
        :meth:`refresh` to get the latest from the server.

        Args:
            name (str): name of wanted repository

        Returns:
            dict: the repository, if found.

        Raises:
            :class:`IndexError`: if no repository named ``name`` is found.

        """
        for r in self._repositories_json:
            if r['name'] == name:
                return r

        raise IndexError

    def refresh(self):
        """
        Refresh local list of repositories with latest from service. A raw
        representation of repositories can be fetched using :meth:`raw_list`.
        """
        response = self._client.http_get('repositories')
        if response.status_code != 200:
            raise exception.NexusClientAPIError(response.content)

        self._repositories_json = response.json()

    def raw_list(self):
        """
        A raw representation of the Nexus repositories.

        Returns:
            dict: for the format, see `List Repositories
            <https://help.sonatype.com/repomanager3/rest-and-integration-api/repositories-api#RepositoriesAPI-ListRepositories>`_.
        """
        self.refresh()
        return self._repositories_json

    def delete(self, name):
        """
        Delete a repository.

        :param name: name of the repository to be deleted.
        :type name: str
        """
        content = nexus_util.groovy_script(SCRIPT_NAME_DELETE)
        self._client.scripts.create_if_missing(SCRIPT_NAME_DELETE, content)
        self._client.scripts.run(SCRIPT_NAME_DELETE, data=name)

    def delete_assets(self, reponame, assetRegex, isWildcard, dryRun):
        """
        Delete assets from a repository through a Groovy script

        :param reponame: name of the repository to delete assets from.
        :type reponame: str
        :param assetRegex: wildcard for assets to delete
        :type assetRegex: str
        :param isWildcard: is the assetRegex a regex or a wildcard?
        :type isWildcard: bool
        :param dryRun: do a dry run or delete for real?
        :type dryRun: bool
        """
        content = nexus_util.groovy_script(SCRIPT_NAME_DELETE_ASSETS)
        self._client.scripts.delete(SCRIPT_NAME_DELETE_ASSETS)
        self._client.scripts.create_if_missing(SCRIPT_NAME_DELETE_ASSETS, content)
        
        # prepare JSON for Groovy:
        jsonData = {}
        jsonData['repoName']=reponame
        jsonData['assetRegex']=assetRegex
        jsonData['isWildcard']=isWildcard
        jsonData['dryRun']=dryRun
        groovy_returned_json = self._client.scripts.run(SCRIPT_NAME_DELETE_ASSETS, data=json.dumps(jsonData))
        
        # parse the JSON we got back
        if 'result' not in groovy_returned_json:
            raise exception.NexusClientAPIError(groovy_returned_json)
        script_result = json.loads(groovy_returned_json['result']) # this is actually a JSON: convert to Python dict
        if script_result == None or 'assets' not in script_result:
            raise exception.NexusClientAPIError(groovy_returned_json)
        
        if 'success' in script_result and script_result['success']==False:
            raise exception.NexusClientAPIError(script_result['error'])
        
        assets_list = script_result['assets']
        if assets_list == None:
            assets_list = []
        return assets_list
        
    def create(self, repository):
        """
        Creates a Nexus repository with the given format and type.

        :param repository: the instance containing the settings for the
            repository to be created.
        :type repository: type(repository)Repository
        :raises NexusClientCreateRepositoryError: error creating repository.
        """
        if not issubclass(type(repository), model.Repository):
            raise TypeError(f'{repository} has type {type(repository)}'
                            f' but must be a subclass of Repository')

        content = nexus_util.groovy_script(SCRIPT_NAME_CREATE)
        self._client.scripts.create_if_missing(SCRIPT_NAME_CREATE, content)

        script_args = json.dumps(repository.configuration)
        resp = self._client.scripts.run(SCRIPT_NAME_CREATE, data=script_args)

        result = resp.get('result')
        if result != 'null':
            raise exception.NexusClientCreateRepositoryError(resp)
