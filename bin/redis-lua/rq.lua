local _NAME = 'rq.lua'
local _DESCRIPTION = 'A set of tools to query rq jobs on redis'
local _LICENSE = 'GNU GPL-3'
local _COPYRIGHT = '(c) 2016 Coopengo'
local _USAGE = [[
Usage: only ARGV are used (no KEYS). Possible commands are:

  - help: print this text

  - fail: list failed jobs ids - <queue>

  - q: print queue summary - <queue>
  - qlist: list queue jobs - <queue> [filters]
  - qcount: count queue jobs - <queue> [filters]
  - qtime: time queue execution - <queue> [filters]
  - qarchive: archive queue jobs - <queue> [filters]
  - qremove: clear queue jobs - <queue> [filters]

  - j: show job - <id>
  - jarchive: archive job - <id>
  - jremove: remove job - <id>
]]

-- general

local STATUS = {'wait', 'success', 'fail', 'archive'}

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

-- specific

local broker = {}
broker.patterns = {'rq:job:'}
broker.queue_pattern = 'rq:queue:'
broker.fail_list = 'rq:queue:failed'

broker.show = function(id)
    local ret = {id}
    local ret_pattern = '%s: %s'
    local res = redis.call('HGETALL', broker.patterns[1] .. id)
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

broker.prepare = function(id)
    local job = {id=id}
    local key = broker.patterns[1] .. id
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

broker.fill = function(id, job)
    local data = redis.call('HGET', broker.patterns[1] .. id, 'coog')
    data = cjson.decode(data)
    local args = data.args
    job.task = data.func
    job.context = args[1]
    job.records = cjson.encode(args[2])
    job.args = cjson.encode(args[3])
    job.result = 'pickled!'
end

local parse_date = function(d)
    local pattern = '(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)'
    return d:match(pattern)
end

broker.time = function(id)
    local key = broker.patterns[1] .. id
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

broker.archive = function(id, force)
    if not force then
        local job = broker.prepare(id)
        assert(job.status ~= STATUS[1], 'archiving a waiting job: no sense')
    end
    local key = broker.patterns[1] .. id
    redis.call('HSET', key, 'status', STATUS[#STATUS])
    redis.call('LREM', broker.fail_list, 0, id)
    return string.format('archived %s', id)
end

broker.remove = function(id)
    redis.call('DEL', broker.patterns[1] .. id)
    redis.call('LREM', broker.fail_list, 0, id)
    return string.format('deleted %s', id)
end

-- api

local api = {}

api.help = function()
    return string.format('%s: %s\n\n%s', _NAME, _DESCRIPTION, _USAGE)
end

api.fail = function(queue)
    assert(queue, 'missing queue')
    local filter = check_filter({2, 1})
    local result = {}
    local fails = redis.call('LRANGE', broker.fail_list, 0, -1)
    for _, id in ipairs(fails) do
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            result[#result+1] = id
        end
    end
    return result
end

api.q = function(queue)
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

api.qlist = function(queue, ...)
    assert(queue, 'missing queue')
    local filter = check_filter({0, 1}, ...)

    local header = {'queue', 'id', 'status', 'context', 'records', 'args',
        'result'}
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

api.qcount = function(queue, ...)
    assert(queue, 'missing queue')
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

api.qtime = function(queue, ...)
    assert(queue, 'missing queue')
    local filter = check_filter({0, 1}, ...)

    local result = 0
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            local t = broker.time(id)
            result = math.max(result, t)
        end
    end
    return result
end

api.qarchive = function(queue, ...)
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

api.qremove = function(queue, ...)
    assert(queue, 'missing queue')
    local filter = check_filter({0, 1}, ...)

    if filter[STATUS[1]] then
        redis.call('DEL', broker.queue_pattern .. queue)
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

local function generate_job_api(act)
    return function(id)
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

api.j = generate_job_api('show')
api.jarchive = generate_job_api('archive')
api.jremove = generate_job_api('remove')

-- main

local command = table.remove(ARGV, 1)
if not command then
    command = 'help'
end
command = assert(api[command], 'Unknown command: ' .. command)
return command(unpack(ARGV))
