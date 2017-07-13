local _NAME = 'celery.lua'
local _DESCRIPTION = 'A set of tools to query celery jobs on redis'
local _LICENSE = 'GNU GPL-3'
local _COPYRIGHT = '(c) 2016 Coopengo'
local _USAGE = [[
Usage: only ARGV are used (no KEYS). Possible commands are:

  - help: print this text

  - list: list jobs inside date interval - <from~to>

  - fail: list failed jobs ids - <queue>
  - flist: list all failed jobs

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

local function parse_criteria(criteria)
    local from, to
    local r = string.find(criteria, '~')
    if r then
        from = string.sub(criteria, 1, r-1)
        if #from == 0 then
            from = nil
        end
        to = string.sub(criteria, r+1)
        if #to == 0 then
            to = nil
        end
    else
        from = criteria
    end
    return from, to
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

local function list_init()
    local header = {'date', 'queue', 'id', 'status', 'context', 'records',
        'args', 'kwargs', 'result'}
    local result = {table.concat(header, '\t')}
    return header, result
end

local function list_append(header, result, job)
    job.id = job.id:sub(1, 8)
    if #job.records > 20 then
        local head = job.records:sub(1, 9)
        local tail = job.records:sub(-9, -1)
        job.records = head .. '..' .. tail
    end
    local item = {}
    for _, k in ipairs(header) do
        item[#item+1] = job[k]
    end
    result[#result+1] = table.concat(item, '\t')
end

-- specific

local broker = {}
broker.patterns = {'coog:job:', 'celery-task-meta-'}
broker.queue_pattern = ''
broker.fail_list = 'coog:fail'

broker.show = function(id)
    local ret = {id}
    ret[#ret+1] = redis.call('GET', broker.patterns[1] .. id)
    ret[#ret+1] = redis.call('GET', broker.patterns[2] .. id)
    if not ret[#ret] then
        ret[#ret] = '!!! never executed !!!'
    end
    return ret
end

broker.prepare = function(id)
    local job = redis.call('GET', broker.patterns[1] .. id)
    job = cjson.decode(job)
    job.id = id
    job.date = job.date or '2000-01-01T00:00:00'
    local meta = redis.call('GET', broker.patterns[2] .. id)
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

broker.fill = function(id, job)
    local args = job.args
    local kwargs = job.kwargs
    job.task = job.func
    job.context = args[1]
    job.records = cjson.encode(args[2])
    job.args = cjson.encode(args[3])
    job.kwargs = cjson.encode(kwargs)
    if job.result then
        job.result = cjson.encode(job.result)
    else
        job.result = '-'
    end
end

broker.time = function(id)
    local job_ttl = redis.call('TTL', broker.patterns[1] .. id)
    local meta_ttl = redis.call('TTL', broker.patterns[2] .. id)
    if job_ttl >= 0 and meta_ttl >= 0 then
        return meta_ttl - job_ttl
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
    local job = cjson.decode(redis.call('GET', key))
    job.status = STATUS[#STATUS]
    redis.call('SET', key, cjson.encode(job))
    redis.call('LREM', broker.fail_list, 0, id)
    return string.format('archived %s', id)
end

broker.remove = function(id)
    redis.call('DEL', broker.patterns[1] .. id)
    redis.call('DEL', broker.patterns[2] .. id)
    redis.call('LREM', broker.fail_list, 0, id)
    return string.format('deleted %s', id)
end

-- api

local api = {}

api.help = function()
    return string.format('%s: %s\n\n%s', _NAME, _DESCRIPTION, _USAGE)
end

api.fail = function(queue)
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

api.list = function(criteria)
    assert(criteria, 'missing criteria')
    local from, to = parse_criteria(criteria)
    local header, result = list_init()

    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if (not from or job.date >= from) and (not to or job.date <= to .. '~') then
            broker.fill(id, job)
            list_append(header, result, job)
        end
    end
    return result
end

api.flist = function()
    local filter = check_filter({2, 1})
    local header, result = list_init()

    local fails = redis.call('LRANGE', broker.fail_list, 0, -1)
    for _, id in ipairs(fails) do
        local job = broker.prepare(id)
        if is_eligible(job, nil, filter) then
            broker.fill(id, job)
            list_append(header, result, job)
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
    local header, result = list_init()

    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if is_eligible(job, queue, filter) then
            broker.fill(id, job)
            list_append(header, result, job)
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
        if #keys == 1 then
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
