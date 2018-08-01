local _NAME = 'report-celery.lua'
local _DESCRIPTION = 'A tool to extract jobs state from redis on a given period'
local _LICENSE = 'GNU GPL-3'
local _COPYRIGHT = '(c) 2018 Coopengo'
local _USAGE = [[
Usage: only ARGV are used (no KEYS). Possible commands are:

  - help: print this text

  - report: provides all jobs state on a given period - <from~to> [pending|success|failed|archive]
]]

-- general

local STATUS = {'pending', 'success', 'failed', 'archive'}

local function parse_time_criteria(criteria)
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

local function parse_extra_criteria(...)
    local criteria = {...}
    if #criteria == 0 then
        return false, false, false, false
    else
        local failed, success, pending, archive = false, false, false, false
        for _, i in ipairs(criteria) do
            if i == 'failed' then
                failed = true
            elseif i == 'success' then
                success = true
            elseif i == 'pending' then
                pending = true
            elseif i == 'archive' then
                archive = true
            end
        end
        return failed, success, pending, archive
    end
end

local function count_nb_records(records)
    local rec = cjson.decode(records)
    return #rec
end

-- celery specific

local broker = {}
broker.patterns = {'coog:job:', 'celery-task-meta-'}
broker.extra_pattern = {'coog:extra:'}
broker.queue_pattern = ''

broker.prepare = function(id)
    local job = redis.call('GET', broker.patterns[1] .. id)
    if not job then
        return nil
    end
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
                job.traceback = meta.traceback or '-'
            end
        end
        job.result = meta.result or '-'
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
    job.chain_name = args[3].chain_name or ''
    if job.result then
        job.result = cjson.encode(job.result)
    else
        job.result = '-'
    end
    job.job_ttl = redis.call('TTL', broker.patterns[1] .. id)
    job.meta_ttl = redis.call('TTL', broker.patterns[2] .. id)
    if job.job_ttl >= 0 and job.meta_ttl >= 0 then
        job.duration_in_sec = job.meta_ttl - job.job_ttl
    else
        job.duration_in_sec = -1
    end
end

broker.get_extra = function(id)
    local job = redis.call('GET', broker.extra_pattern[1] .. id)
    if not job then
        return nil
    end
    job = cjson.decode(job)
    job.id = id
    job.first_launch_date = job.first_launch_date or '2000-01-01T00:00:00'
    return job
end
-- api

local api = {}



local function get_details(from, to, extract_failed, extract_success, extract_pending, extract_archive)
    local summary, failed, success, pending, archive = {}, {}, {}, {}, {}
    local pattern = broker.patterns[1]
    local keys = redis.call('KEYS', pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#pattern+1)
        local job = broker.prepare(id)
        if (not from or job.date >= from) and (not to or job.date <= to .. '~') then
            broker.fill(id, job)
            summary[job.chain_name] = summary[job.chain_name] or {}
            summary[job.chain_name][job.queue] = summary[job.chain_name][job.queue] or {
                failed={
                    nb_jobs=0,
                    nb_records=0},
                success={
                    nb_jobs=0,
                    nb_records=0},
                pending={
                    nb_jobs=0,
                    nb_records=0},
                archive={
                    nb_jobs=0,
                    nb_records=0},
                duration_in_sec=0,
                first_launch_date='9999-01-01T00:00:00'}
            summary[job.chain_name][job.queue][job.status].nb_jobs = summary[job.chain_name][job.queue][job.status].nb_jobs + 1
            summary[job.chain_name][job.queue][job.status].nb_records = summary[job.chain_name][job.queue][job.status].nb_records + count_nb_records(job.records)
            summary[job.chain_name][job.queue].duration_in_sec = math.max(summary[job.chain_name][job.queue].duration_in_sec, job.duration_in_sec)
            if summary[job.chain_name][job.queue].first_launch_date > job.date then
                summary[job.chain_name][job.queue].first_launch_date = job.date
            end
            if extract_failed and job.status == STATUS[3] then
                failed[job.chain_name] = failed[job.chain_name] or {}
                failed[job.chain_name][job.queue] = failed[job.chain_name][job.queue] or {}
                failed[job.chain_name][job.queue][job.id] = job
            end
            if extract_success and job.status == STATUS[2] then
                success[job.chain_name] = success[job.chain_name] or {}
                success[job.chain_name][job.queue] = success[job.chain_name][job.queue] or {}
                success[job.chain_name][job.queue][job.id] = job
            end
            if extract_pending and job.status == STATUS[1] then
                pending[job.chain_name] = pending[job.chain_name] or {}
                pending[job.chain_name][job.queue] = pending[job.chain_name][job.queue] or {}
                pending[job.chain_name][job.queue][job.id] = job
            end
            if extract_archive and job.status == STATUS[4] then
                archive[job.chain_name] = archive[job.chain_name] or {}
                archive[job.chain_name][job.queue] = archive[job.chain_name][job.queue] or {}
                archive[job.chain_name][job.queue][job.id] = job
            end
        end
    end
    local extra_pattern = broker.extra_pattern[1]
    local keys = redis.call('KEYS', extra_pattern .. '*')
    for _, key in ipairs(keys) do
        local id = key:sub(#extra_pattern+1)
        local job = broker.get_extra(id)
        if (not from or job.first_launch_date >= from) and (not to or job.first_launch_date <= to .. '~') then
            summary[job.chain_name] = summary[job.chain_name] or {}
            summary[job.chain_name][job.queue] = summary[job.chain_name][job.queue] or {
                failed={
                    nb_jobs=0,
                    nb_records=0},
                success={
                    nb_jobs=0,
                    nb_records=0},
                pending={
                    nb_jobs=0,
                    nb_records=0},
                archive={
                    nb_jobs=0,
                    nb_records=0},
                duration_in_sec=0,
                first_launch_date='9999-01-01T00:00:00'}
            summary[job.chain_name][job.queue][job.status].nb_jobs = summary[job.chain_name][job.queue][job.status].nb_jobs + job.nb_jobs
            summary[job.chain_name][job.queue][job.status].nb_records = summary[job.chain_name][job.queue][job.status].nb_records + job.nb_records
            summary[job.chain_name][job.queue].duration_in_sec = math.max(summary[job.chain_name][job.queue].duration_in_sec, job.duration_in_sec)
            if summary[job.chain_name][job.queue].first_launch_date > job.first_launch_date then
                summary[job.chain_name][job.queue].first_launch_date = job.first_launch_date
            end
        end
    end
    return summary, failed, success, pending, archive
end

api.report = function(time_criteria, ...)
    -- read params
    assert(time_criteria, 'missing criteria')
    local from, to = parse_time_criteria(time_criteria)
    local extract_failed, extract_success, extract_pending, extract_archive = parse_extra_criteria(...)

    local result = {}
    result['from'] = from
    result['to'] = to
    local summary, failed, success, pending, archive = get_details(from, to, extract_failed, extract_success, extract_pending, extract_archive)
    result['summary'] = summary
    if extract_archive then
        result['archive'] = archive
    end
    if extract_success then
        result['success'] = success
    end
    if extract_pending then
        result['pending'] = pending
    end
    if extract_failed then
        result['failed'] = failed
    end
    return cjson.encode(result)
end

api.help = function()
    print(string.format('%s: %s\n\n%s', _NAME, _DESCRIPTION, _USAGE))
end

-- main

local command = table.remove(ARGV, 1)

if not command then
    command = 'help'
end
command = assert(api[command], 'Unknown command: ' .. command)
return command(unpack(ARGV))
