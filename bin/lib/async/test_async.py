from async.tasks import _batch_split


def test_batch_split():
    assert list(_batch_split(
        [[1], [2], [3], [4], [5], [6], [7]], 2)) == \
        [[1, 2], [3, 4], [5, 6], [7]]
    assert list(_batch_split(
        [[1, 2, 3, 4, 5], [6], [7]], 0)) == [[1, 2, 3, 4, 5, 6, 7]]
    assert list(_batch_split(
        [[1, 2, 3, 4, 5], [6], [7]], 1)) == [[1, 2, 3, 4, 5], [6], [7]]
    assert list(_batch_split(
        [[1, 2, 3, 4, 5], [6], [7]], 2)) == [[1, 2, 3, 4, 5], [6, 7]]
    assert list(_batch_split(
        [[1, 2, 3, 4, 5], [6], [7]], 3)) == [[1, 2, 3, 4, 5], [6, 7]]
    assert list(_batch_split(
        [[6], [7], [1, 2, 3, 4, 5]], 2)) == [[6, 7], [1, 2, 3, 4, 5]]
    assert list(_batch_split(
        [[6], [7], [1, 2, 3, 4, 5]], 3)) == [[6, 7], [1, 2, 3, 4, 5]]
    assert list(_batch_split(
        [[6], [1, 2, 3, 4, 5], [7], [8]], 2)) == [[6], [1, 2, 3, 4, 5], [7, 8]]
