local _NAME = 'batch.lua'
local _DESCRIPTION = 'A set of tools to query batch jobs on redis'
local _LICENSE = 'GNU GPL-3'
local _COPYRIGHT = '(c) 2016 Coopengo'
local _USAGE = [[
Usage: only ARGV are used (no KEYS). Possible commands are:

  - help: print this text
  - list: list queue jobs - <broker> <queue> [filters]
  - count: count queue jobs - <broker> <queue> [filters]
  - waiting: count waiting jobs - <broker> <queue>
  - backup: archive queue jobs - <broker> <queue> [filters]
  - clear: clear queue jobs - <broker> <queue> [filters]
  - summary: print queue summary - <broker> <queue>
  - key: print job key - <broker> <id>
  - show: show job - <broker> <id>
  - archive: archive job - <broker> <id>
  - remove: remove job - <broker> <id>
]]

-- utils

local parse_date = function(d)
    local pattern = '(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)'
    return d:match(pattern)
end

-- broker specificities

local STATUS = {'wait', 'success', 'fail', 'archive'}

local broker_api = {rq={}, celery={}}

broker_api.rq.patterns = {'rq:job:'}

broker_api.rq.dequeue = function(q)
    redis.call('DEL', 'rq:queue:' .. q)
end

broker_api.rq.show = function(id)
    local ret = {id}
    local ret_pattern = '%s: %s'
    local res = redis.call('HGETALL', broker_api.rq.patterns[1] .. id)
    local key
    for i, v in ipairs(res) do
        if i % 2 == 1 then
            key = v
        else
            ret[#ret+1] = ret_pattern:format(key, v)
        end
    end
    return ret
end

broker_api.rq.prepare = function(id)
    local job = {id=id}
    local key = broker_api.rq.patterns[1] .. id
    job.queue = redis.call('HGET', key, 'origin')
    local status = redis.call('HGET', key, 'status')
    if status == 'queued' or status == 'started' then
        job.status = STATUS[1]
    elseif status == 'finished' then
        job.status = STATUS[2]
    elseif status == 'failed' then
        job.status = STATUS[3]
    else
        job.status = status
    end
    return job
end

broker_api.rq.fill = function(id, job)
    local data = redis.call('HGET', broker_api.rq.patterns[1] .. id, 'coog')
    data = cjson.decode(data)
    local args = data.args
    job.task = data.func
    job.connect = args[2]
    job.treat = args[3]
    job.args = cjson.encode(args[4])
    job.records = table.concat(args[5], ',')
    job.result = 'pickled!'
end

broker_api.rq.time = function(id)
    local key = broker_api.rq.patterns[1] .. id
    local enqueued = redis.call('HGET', key, 'enqueued_at')
    local ended = redis.call('HGET', key, 'ended_at')
    if enqueued and ended then
        local qy, qm, qd, qh, qmn, qs = parse_date(enqueued)
        local ey, em, ed, eh, emn, es = parse_date(ended)
        local res = es-qs + 60*(emn -qmn) + 3600*(eh-qh)
        if res < 0 then
            -- day change
            res = res + 24*3600
        end
        return res
    else
        return -1
    end
end

broker_api.rq.archive = function(id, force)
    if not force then
        local job = broker_api.rq.prepare(id)
        assert(job.status ~= STATUS[1], 'archiving a waiting job: no sense')
    end
    local key = broker_api.rq.patterns[1] .. id
    redis.call('HSET', key, 'status', STATUS[#STATUS])
    return string.format('archived %s', id)
end

broker_api.rq.remove = function(id)
    redis.call('DEL', broker_api.rq.patterns[1] .. id)
    return string.format('deleted %s', id)
end

broker_api.rq.waiting = function(queue)
    return redis.call('LLEN', 'rq:queue:' .. queue)
end

broker_api.celery.patterns = {'coog:job:', 'celery-task-meta-'}

broker_api.celery.dequeue = function(q)
    redis.call('DEL', q)
end

broker_api.celery.show = function(id)
    local ret = {id}
    ret[#ret+1] = redis.call('GET', broker_api.celery.patterns[1] .. id)
    ret[#ret+1] = redis.call('GET', broker_api.celery.patterns[2] .. id)
    if not ret[#ret] then
        ret[#ret] = '!!! never executed !!!'
    end
    return ret
end

broker_api.celery.prepare = function(id)
    local job = redis.call('GET', broker_api.celery.patterns[1] .. id)
    job = cjson.decode(job)
    job.id = id
    local meta = redis.call('GET', broker_api.celery.patterns[2] .. id)
    if meta then
        meta = cjson.decode(meta)
        if not job.status then
            if meta.status == 'SUCCESS' then
                job.status = STATUS[2]
            else
                job.status = STATUS[3]
            end
        end
        job.result = meta.result
    else
        job.status = job.status or STATUS[1]
    end
    return job
end

broker_api.celery.fill = function(id, job)
    local args = job.args
    job.task = job.func
    job.connect = args[2]
    job.treat = args[3]
    job.args = cjson.encode(args[4])
    job.records = table.concat(args[5], ',')
    if job.result then
        job.result = cjson.encode(job.result)
    else
        job.result = '-'
    end
end

broker_api.celery.time = function(id)
    local job_ttl = redis.call('TTL', broker_api.celery.patterns[1] .. id)
    local meta_ttl = redis.call('TTL', broker_api.celery.patterns[2] .. id)
    if job_ttl >= 0 and meta_ttl >= 0 then
        return meta_ttl - job_ttl
    else
        return -1
    end
end

broker_api.celery.archive = function(id, force)
    if not force then
        local job = broker_api.rq.prepare(id)
        assert(job.status ~= STATUS[1], 'archiving a waiting job: no sense')
    end
    local key = broker_api.celery.patterns[1] .. id
    local job = cjson.decode(redis.call('GET', key))
    job.status = STATUS[#STATUS]
    redis.call('SET', key, cjson.encode(job))
    return string.format('archived %s', id)
end

broker_api.celery.remove = function(id)
    redis.call('DEL', broker_api.celery.patterns[1] .. id)
    redis.call('DEL', broker_api.celery.patterns[2] .. id)
    return string.format('deleted %s', id)
end

broker_api.celery.waiting = function(queue)
    return redis.call('LLEN', queue)
end

-- helpers

local function check_broker(broker)
    assert(broker, 'missing queue broker')
    return assert(broker_api[broker], 'unknown queue broker')
end

local function check_filter(default, ...)
    local filters = {...}
    -- tricky behaviour
    --   empty filter and default=nil    => crash
    --   empty filter and default={n, m} => STATUS[1+n], ..., STATUS[#-m]
    if #filters == 0 then
        assert(default, 'no filters')
        for i = 1+default[1], #STATUS-default[2] do
            filters[#filters+1] = STATUS[i]
        end
    end
    local filter = {}
    for _, status in ipairs(filters) do
        filter[status] = true
    end
    return filter
end

local function is_eligible(job, queue, filter)
    if queue and job.queue ~= queue then
        return false
    end
    return filter[job.status]
end

local function generate_job_api(act)
    return function(broker, id)
        local broker = check_broker(broker)
        assert(id, 'missing job id')
        local pattern = broker.patterns[1]
        local keys = redis.call('KEYS', pattern .. id .. '*')
        if #keys > 1 then
            local ret = {string.format('%d jobs matching', #keys)}
            for _, key in ipairs(keys) do
                ret[#ret+1] = key:sub(#pattern+1)
            end
            return ret
        elseif #keys == 0 then
            return 'no jobs matching'
        elseif #keys == 1 then
            local key = keys[1]
            local id = key:sub(#pattern+1)
            return broker[act](id)
        end
    end
end

-- api

local api = {}

api.help = function()
    return string.format('%s: %s\n\n%s', _NAME, _DESCRIPTION, _USAGE)
end

api.list = function(broker, queue, ...)
    broker = check_broker(broker)
    if queue == 'all' then
        queue = nil
    end
    local filter = check_filter({0, 1}, ...)

    local header = {'queue', 'id', 'status', 'connect', 'treat', 'args',
        'records', 'result'}
    local result = {table.concat(header, '\t')}

    local function insert(job)
        job.id = job.id:sub(1, 8)
        if #job.records > 20 then
            local head = job.records:sub(1, 9)
            local tail = job.records:sub(-9, -1)
            job.records =  head .. '..' .. tail
        end
        local item = {}
        for _, k in ipairs(header) do
            item[#item+1] = job[k]
        end
        result[#result+1] = table.concat(item, '\t')
    end

    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            broker.fill(id, job)
            insert(job)
        end
    end
    return result
end

api.count = function(broker, queue, ...)
    broker = check_broker(broker)
    if queue == 'all' then
        queue = nil
    end
    local filter = check_filter({0, 1}, ...)

    local result = 0
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            result = result + 1
        end
    end
    return result
end

api.waiting = function(broker, queue)
    broker = check_broker(broker)
    assert(queue, 'missing queue')
    return broker.waiting(queue)
end

api.backup = function(broker, queue, ...)
    broker = check_broker(broker)
    assert(queue, 'missing queue')
    local filter = check_filter({1, 2}, ...)
    assert(not filter[STATUS[1]], 'archiving waiting jobs: no sense')

    local result = 0
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            result = result + 1
            broker.archive(id, true)
        end
    end
    return string.format('%d jobs archived', result)
end

api.clear = function(broker, queue, ...)
    broker = check_broker(broker)
    assert(queue, 'missing queue')
    local filter = check_filter({0, 1}, ...)

    if filter[STATUS[1]] then
        broker.dequeue(queue)
    end

    local result = 0
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            result = result + 1
            broker.remove(id)
        end
    end
    return string.format('%d jobs removed', result)
end

api.summary = function(broker, queue)
    broker = check_broker(broker)
    assert(queue, 'missing queue')
    local filter = check_filter({0, 1})

    local wait = 0
    local success = 0
    local fail = 0
    local time = 0

    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            local tm = -1
            if job.status == STATUS[1] then
                wait = wait + 1
            elseif job.status == STATUS[2] then
                success = success + 1
                tm = broker.time(id)
            elseif job.status == STATUS[3] then
                fail = fail + 1
                tm = broker.time(id)
            end
            if tm > time then
                time = tm
            end
        end
    end

    local hr = math.floor(time/3600)
    local mn = math.floor((time%3600)/60)
    local se = time%60

    local ret_pattern = [[
    wait       %s jobs
    success    %d jobs
    fail       %d jobs
    time       %dh %dm %ds]]
    return ret_pattern:format(wait, success, fail, hr, mn, se)
end

api.key = function(broker, id)
    local broker = check_broker(broker)
    assert(id, 'missing job id')
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. id .. '*')
    if #keys == 1 then
        return keys[1]
    end
end

api.show = generate_job_api('show')
api.archive = generate_job_api('archive')
api.remove = generate_job_api('remove')

-- main

local command = table.remove(ARGV, 1)
if not command then
    command = 'help'
end
command = assert(api[command], 'Unknown command: ' .. command)
return command(unpack(ARGV))
