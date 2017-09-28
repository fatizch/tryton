import os

JOB_TIMEOUT = 60 * 60              # job exec time <= 1h is default
if 'COOG_JOB_TIMEOUT' in os.environ:
    # job custom exec time in seconds
    JOB_TIMEOUT = int(os.environ['COOG_JOB_TIMEOUT'])

JOB_TTL = 24 * 60 * 60             # job queue wait time <= 1d
JOB_RESULT_TTL = 5 * 24 * 60 * 60  # job result wait time <= 5d
