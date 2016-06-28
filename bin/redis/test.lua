local _NAME = 'test.lua'
local _DESCRIPTION = 'A set of tools to query test jobs on redis'
local _LICENSE = 'GNU GPL-3'
local _COPYRIGHT = '(c) 2016 Coopengo'
local _USAGE = [[
Usage: only ARGV are used (no KEYS). Possible commands are:

  - help: print this text
  - key: print job key - <id>
  - show: show job - <id>
  - list: list queue jobs - [filters]
  - count: count queue jobs - [filters]
  - summary: print queue summary
  - remove: remove job - <id>
  - clear: remove queue jobs - [filters]
  - archive: archive job - <id>
  - backup: archive queue jobs - [filters]
]]

-- utils

local STATUS = {'wait', 'success', 'fail'}
local QUEUE = 'test'
local PATTERN = 'rq:job:'

local function create_filter(...)
    local filter = {...}
    if #filter == 0 then
        filter = STATUS
    end
    local res = {}
    for _, st in ipairs(filter) do
        res[st] = true
    end
    return res
end

local function is_eligible(job, filter)
    if job.queue ~= QUEUE then
        return false
    end
    return filter[job.status]
end

local function prepare(id)
    local job = {id=id}
    local key = PATTERN..id
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

local function parse_date(d)
    local pattern = '(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)'
    return d:match(pattern)
end

local function diff_dates(to, from)
    if from and to then
        local fy, fm, fd, fh, fmn, fs = parse_date(from)
        local ty, tm, td, th, tmn, ts = parse_date(to)
        local res = ts-fs + 60*(tmn -fmn) + 3600*(th-fh)
        if res < 0 then
            -- day change
            res = res + 24*3600
        end
        return res
    else
        return -1
    end
end

local function get_time(id)
    local key = PATTERN..id
    local enqueued = redis.call('HGET', key, 'enqueued_at')
    local ended = redis.call('HGET', key, 'ended_at')
    return diff_dates(ended, enqueued)
end

local function fill(id, job)
    local data = redis.call('HGET', PATTERN..id, 'coog')
    data = cjson.decode(data)
    local args = data.args
    job.task = data.func
    job.module = args[1]
    job.started = redis.call('HGET', PATTERN..id, 'started_at')
    job.ended = redis.call('HGET', PATTERN..id, 'ended_at')
    job.time = diff_dates(job.ended, job.started)
    local result = redis.call('HGET', PATTERN..id, 'coog-result')
    if result then
        result = cjson.decode(result)
        job.total = result.total
        job.fails = result.fails
        job.errors = result.errors
    end
end

local function dequeue()
    local q = 'rq:queue:'..QUEUE
    redis.call('DEL', q)
    redis.call('SREM', 'rq:queues', q)
end

-- helpers

local function show(id)
    local ret = {id}
    local ret_pattern = '%s: %s'
    local res = redis.call('HGETALL', PATTERN..id)
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

local function remove(id)
    redis.call('DEL', PATTERN..id)
    return string.format('deleted %s', id)
end

local function archive(id)
    redis.call('HSET', PATTERN..id, 'status', 'archive')
    return string.format('archived %s', id)
end

local function generate_job_api(fn)
    return function(id)
        assert(id, 'missing job id')
        local keys = redis.call('KEYS', PATTERN..id..'*')
        if #keys > 1 then
            local ret = {string.format('%d jobs matching', #keys)}
            for _, key in ipairs(keys) do
                ret[#ret+1] = key:sub(#PATTERN+1)
            end
            return ret
        elseif #keys == 0 then
            return 'no jobs matching'
        elseif #keys == 1 then
            local key = keys[1]
            local id = key:sub(#PATTERN+1)
            return fn(id)
        end
    end
end

-- api

local api = {}

api.help = function()
    return string.format('%s: %s\n\n%s', _NAME, _DESCRIPTION, _USAGE)
end

api.key = function(id)
    assert(id, 'missing job id')
    local keys = redis.call('KEYS', PATTERN..id..'*')
    if #keys == 1 then
        return keys[1]
    end
end

api.show = generate_job_api(show)

api.list = function(...)
    local filter = create_filter(...)
    local header = {'queue', 'id', 'status', 'module', 'started', 'ended',
    'time', 'total', 'fails', 'errors'}
    local result = {table.concat(header, '\t')}

    local function insert(job)
        job.id = job.id:sub(1, 8)
        local item = {}
        for _, k in ipairs(header) do
            item[#item+1] = job[k] or '-'
        end
        result[#result+1] = table.concat(item, '\t')
    end

    local keys = redis.call('KEYS', PATTERN..'*')
    for _, key in ipairs(keys) do
        local id = key:sub(#PATTERN+1)
        local job = prepare(id)
        if is_eligible(job, filter) then
            fill(id, job)
            insert(job)
        end
    end
    return result
end

api.count = function(...)
    local filter = create_filter(...)
    local result = 0
    local keys = redis.call('KEYS', PATTERN..'*')
    for _, key in ipairs(keys) do
        local id = key:sub(#PATTERN+1)
        local job = prepare(id)
        if is_eligible(job, filter) then
            result = result + 1
        end
    end
    return ''..result
end

api.summary = function()
    local filter = create_filter()
    local wait = 0
    local success = 0
    local fail = 0
    local time = 0
    local keys = redis.call('KEYS', PATTERN..'*')
    for _, key in ipairs(keys) do
        local id = key:sub(#PATTERN+1)
        local job = prepare(id)
        if is_eligible(job, filter) then
            local tm = -1
            if job.status == STATUS[1] then
                wait = wait + 1
            elseif job.status == STATUS[2] then
                success = success + 1
                tm = get_time(id)
            elseif job.status == STATUS[3] then
                fail = fail + 1
                tm = get_time(id)
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

api.remove = generate_job_api(remove)

api.clear = function(...)
    local filter = create_filter(...)
    if filter[STATUS[1]] then
        dequeue()
    end
    local result = 0
    local keys = redis.call('KEYS', PATTERN..'*')
    for _, key in ipairs(keys) do
        local id = key:sub(#PATTERN+1)
        local job = prepare(id)
        if is_eligible(job, filter) then
            result = result + 1
            remove(id)
        end
    end
    return string.format('%d jobs removed', result)
end

api.archive = generate_job_api(archive)

api.backup = function(...)
    local filter = create_filter(...)
    if filter[STATUS[1]] then
        dequeue()
    end
    local result = 0
    local keys = redis.call('KEYS', PATTERN..'*')
    for _, key in ipairs(keys) do
        local id = key:sub(#PATTERN+1)
        local job = prepare(id)
        if is_eligible(job, filter) then
            result = result + 1
            archive(id)
        end
    end
    return string.format('%d jobs archived', result)
end

-- main

local command = table.remove(ARGV, 1)
if not command then
    command = 'help'
end
command = assert(api[command], 'Unknown command: '..command)
return command(unpack(ARGV))
