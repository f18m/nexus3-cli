import itertools
import pytest

from nexuscli import nexus_util
from nexuscli.nexus_util import calculate_hash, filtered_list_gen


@pytest.mark.parametrize('artefact_path,x_count', [
    (None,              0),
    (['not a string'],  0),
    (999,               0),
    ('some path',       1),
])
def test_filtered_list_gen(artefact_path, x_count):
    raw_response = [{'path': artefact_path}]

    filtered_artefacts = filtered_list_gen(raw_response)

    assert x_count == sum(1 for _ in filtered_artefacts)


@pytest.mark.parametrize('artefact_path, starts_with, x_count', [
    ('some path/',          '',           1),
    ('some path/some file', '',           1),
    ('some path/',          'some ',      1),
    ('some path/',          'some path',  1),
    ('some path/',          'some path/', 1),
    ('some path/some file', 'some file',  0),
    ('some path', 'path',                 0),
    ('👌 ugh tf', '👌',                    1),
    ('😝',        '👌',                    0),
])
def test_filtered_list_gen_starts_with(
        artefact_path, starts_with, x_count):
    raw_response = [{'path': artefact_path}]

    filtered_artefacts = filtered_list_gen(raw_response, starts_with)

    assert x_count == sum(1 for _ in filtered_artefacts)


@pytest.mark.parametrize('hash_name, x_hash', [
    ('md5', '56c7e01b8db73367c174401f196a99ff'),
    ('sha1', 'e440325381d729a7f328bb6d3b8fdbe2fbe2ce74'),
    ('sha256',
     'dcdb8c8f2f95f40f311edd7c7d613a02a3cc5277d67a30e0d0a7bf88cae09b97'),
])
def test__calculate_hash(hash_name, x_hash, nexus_mock_client):
    """
    Ensure the method returns the correct hash for each algorithm using a known
    file with hash generated using another tool (MacOS shasum and md5 cli).
    """
    fixture = 'tests/fixtures/manifest-target/foo/bar.txt'

    sha1_file = calculate_hash(hash_name, fixture)
    with open(fixture, 'rb') as fh:
        sha1_fh = calculate_hash(hash_name, fh)

    assert sha1_fh == sha1_file
    assert sha1_fh == x_hash


@pytest.mark.parametrize('hash_name, match',
                         itertools.product(['sha1', 'md5'], [True, False]))
def test_has_same_hash(hash_name, match, mocker, faker):
    """Ensure method returns True when checksum matches and False otherwise"""
    file_path = faker.file_path()
    remote_hash = getattr(faker, hash_name)()
    if match:
        local_hash = remote_hash
    else:
        local_hash = getattr(faker, hash_name)()

    mocker.patch('nexuscli.nexus_util.calculate_hash', return_value=local_hash)
    artefact = {'checksum': {hash_name: remote_hash}}

    assert match == nexus_util.has_same_hash(artefact, file_path)
    nexus_util.calculate_hash.assert_called_with(hash_name, file_path)


def test_has_same_hash_empty():
    """Ensure method returns false when artefact has no checksum entries"""
    assert not nexus_util.has_same_hash({}, 'any')


@pytest.mark.parametrize('is_dir', [True, False])
def test_ensure_exists(is_dir, tmp_path, faker):
    """Ensure method calls the right combination of mkdir/touch"""
    path = tmp_path.joinpath(faker.word())

    nexus_util.ensure_exists(path, is_dir=is_dir)

    assert path.exists()
    assert is_dir == path.is_dir()
    assert is_dir != path.is_file()
