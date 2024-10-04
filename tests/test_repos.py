import csv
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from repos import (
    main, get_repos, pager, truncate_description,
    write_csv, parse_link_header
)


@patch('repos.requests.get')
def test_get_repos_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'items': []}
    mock_get.return_value = mock_response

    url = 'https://api.github.com/search/repositories'
    response = get_repos(url)
    assert response.status_code == 200
    assert response.json() == {'items': []}


@patch('repos.requests.get')
def test_get_repos_rate_limit(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.headers = {'x-ratelimit-reset': str(int(datetime.now().timestamp()) + 1)}
    mock_get.return_value = mock_response

    url = 'https://api.github.com/search/repositories'
    with patch('repos.sleep', return_value=None):
        response = get_repos(url)
        assert response.status_code == 403


def test_parse_link_header():
    link_header = '<https://api.github.com/search/repositories?page=2>; rel="next", <https://api.github.com/search/repositories?page=34>; rel="last"'
    links = parse_link_header(link_header)
    assert links['next'] == 'https://api.github.com/search/repositories?page=2'
    assert links['last'] == 'https://api.github.com/search/repositories?page=34'


@patch('repos.get_repos')
def test_pager(mock_get_repos):
    mock_response = MagicMock()
    mock_response.json.return_value = {'total_count': 2, 'items': [{'full_name': 'repo1'}, {'full_name': 'repo2'}]}
    mock_response.headers = {'Link': ''}
    mock_get_repos.return_value = mock_response

    url = 'https://api.github.com/search/repositories'
    params = {'q': 'test'}
    repos = list(pager(url, params))
    assert len(repos) == 2
    assert repos[0]['full_name'] == 'repo1'
    assert repos[1]['full_name'] == 'repo2'


def test_truncate_description():
    description = "This is a very long description that needs to be truncated."
    truncated = truncate_description(description, 20)
    assert truncated == "This is a very lo..."

    description = "Short description."
    truncated = truncate_description(description, 20)
    assert truncated == "Short description."

    description = None
    truncated = truncate_description(description, 20)
    assert truncated == ""


@patch('repos.csv.writer')
def test_write_csv(mock_csv_writer):
    repos = [
        {
            'full_name': 'repo1',
            'description': 'description1',
            'stargazers_count': 10,
            'language': 'Python',
            'updated_at': '2023-01-01T00:00:00Z',
            'html_url': 'https://github.com/repo1',
        },
        {
            'full_name': 'repo2',
            'description': 'description2',
            'stargazers_count': 20,
            'language': 'JavaScript',
            'updated_at': '2023-01-02T00:00:00Z',
            'html_url': 'https://github.com/repo2',
        },
    ]
    mock_writer_instance = MagicMock()
    mock_csv_writer.return_value = mock_writer_instance

    write_csv(repos, 'test.csv')
    mock_writer_instance.writerow.assert_any_call(
        ['full_name', 'description', 'stargazers_count', 'language', 'updated_at', 'url']
    )
    mock_writer_instance.writerow.assert_any_call(
        ['repo2', 'description2', 20, 'JavaScript', '2023-01-02T00:00:00Z', 'https://github.com/repo2']
    )
    mock_writer_instance.writerow.assert_any_call(
        ['repo1', 'description1', 10, 'Python', '2023-01-01T00:00:00Z', 'https://github.com/repo1']
    )


@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'fake_token')
    monkeypatch.setenv('QUERY', 'test_query')
    monkeypatch.setenv('PER_PAGE', '2')
    monkeypatch.setenv('CSV_FILE', 'test_output.csv')


@patch('repos.requests.get')
def test_main_integration(mock_get, mock_environment):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'total_count': 2,
        'items': [
            {
                'full_name': 'test/repo1',
                'description': 'Test repo 1',
                'stargazers_count': 10,
                'language': 'Python',
                'updated_at': '2023-01-01T00:00:00Z',
                'html_url': 'https://github.com/test/repo1',
            },
            {
                'full_name': 'test/repo2',
                'description': 'Test repo 2',
                'stargazers_count': 20,
                'language': 'JavaScript',
                'updated_at': '2023-01-02T00:00:00Z',
                'html_url': 'https://github.com/test/repo2',
            },
        ],
    }
    mock_response.headers = {'Link': ''}
    mock_get.return_value = mock_response

    # Print environment variables for debugging
    print("Environment variables:")
    print(f"GITHUB_TOKEN: {os.environ.get('GITHUB_TOKEN')}")
    print(f"QUERY: {os.environ.get('QUERY')}")
    print(f"PER_PAGE: {os.environ.get('PER_PAGE')}")
    print(f"CSV_FILE: {os.environ.get('CSV_FILE')}")

    # Run the main function
    main()

    # Check that the CSV file was created
    output_file = Path('test_output.csv')
    print(f"Current working directory: {os.getcwd()}")
    print(f"Expected output file: {output_file.absolute()}")
    assert output_file.exists(), f"Output file {output_file.absolute()} does not exist"

    # Read the CSV file and check its contents
    with output_file.open('r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

        # Check the header
        assert rows[0] == ['full_name', 'description', 'stargazers_count', 'language', 'updated_at', 'url']

        # Check the data rows
        assert rows[1] == [
            'test/repo2',
            'Test repo 2',
            '20',
            'JavaScript',
            '2023-01-02T00:00:00Z',
            'https://github.com/test/repo2',
        ]
        assert rows[2] == ['test/repo1', 'Test repo 1', '10', 'Python', '2023-01-01T00:00:00Z', 'https://github.com/test/repo1']

    # Clean up: remove the test output file
    output_file.unlink()

    # Verify that the API was called with the correct parameters
    mock_get.assert_called_once_with(
        'https://api.github.com/search/repositories',
        params={'q': 'test_query', 'per_page': 2, 'sort': 'stars', 'order': 'desc'},
        headers={'Accept': 'application/vnd.github.v3+json', 'Authorization': 'token fake_token'},
    )
