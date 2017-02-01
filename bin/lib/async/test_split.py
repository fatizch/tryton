from async.tasks import split_batch, split_job


def test_split_batch():
    assert list(split_batch(
            [1, 2, 3, 4, 5, 6, 7], 2)) == \
            [[1, 2], [3, 4], [5, 6], [7]]
    assert list(split_batch(
            [[1, 2, 3, 4, 5], 6, 7], 0)) == \
            [[1, 2, 3, 4, 5, 6, 7]]
    assert list(split_batch(
            [[1, 2, 3, 4, 5], 6, 7], 1)) == \
            [[1, 2, 3, 4, 5], [6], [7]]
    assert list(split_batch(
            [[1, 2, 3, 4, 5], 6, 7], 2)) == \
            [[1, 2, 3, 4, 5], [6, 7]]
    assert list(split_batch(
            [[1, 2, 3, 4, 5], 6, 7], 3)) == \
            [[1, 2, 3, 4, 5], [6, 7]]
    assert list(split_batch(
            [6, 7, [1, 2, 3, 4, 5]], 2)) == \
            [[1, 2, 3, 4, 5], [6, 7]]
    assert list(split_batch(
            [6, 7, [1, 2, 3, 4, 5]], 3)) == \
            [[1, 2, 3, 4, 5], [6, 7]]
    assert list(split_batch(
            [6, [1, 2, 3, 4, 5], 7, 8], 2)) == \
            [[1, 2, 3, 4, 5], [6, 7], [8]]
    assert list(split_batch(
            [(1,), (2,), (3,), (4,), (5,)], 2)) == \
            [[(1,), (2,)], [(3,), (4,)], [(5,)]]
    assert list(split_batch(
            (i for i in xrange(5)), 2)) == \
            [[0, 1], [2, 3], [4]]


def test_split_job():
    assert list(split_job(
        [1, 2, 3, 4, 5], 2)) == \
        [[1, 2], [3, 4], [5]]
    assert list(split_job(
        [[1], [2], [3], [4, 5]], 2)) == \
        [[[1], [2]], [[3], [4, 5]]]
