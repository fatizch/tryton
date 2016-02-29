--[[

Description: list celery jobs in Redis (this script executes inside redis)
Arguments:
- <queue>: jobs queue (all is accepted)
- [filter*]: job status list to filter result

--]]

local queue = ARGV[1]
if queue == 'all' then
    queue = nil
end

local check_status = false
local status = {}
if #ARGV > 1 then
    check_status = true
    for i = 2, #ARGV do
        status[ARGV[i]] = true
    end
end

local result = {}
local header = {'task', 'job', 'status', 'connect', 'treat', 'ids' , 'extra',
    'result'}
table.insert(result, table.concat(header, '\t'))

local function insert_job(key, job)
    -- retrieve data and fill o object
    local o = {job=key, status=job.status}
    local args = job.args
    o.task = args[1]
    o.ids = table.concat(args[2], ',')
    o.connect = args[3]
    o.treat = args[4]
    o.extra = cjson.encode(args[5])
    if job.result then
        o.result = cjson.encode(job.result)
    else
        o.result = '-'
    end
    -- format raw according to header
    local item = {}
    for _, k in ipairs(header) do
        table.insert(item, o[k])
    end
    table.insert(result, table.concat(item, '\t'))
end

local function is_eligible(job)
    return (queue == nil or job.queue == queue) and (not check_status or
    status[job.status] ~= nil)
end

local function fill_status(key, job)
    local res = redis.call('GET', 'celery-task-meta-' .. key)
    if res then
        res = cjson.decode(res)
        if res.status == 'SUCCESS' then
            job.status = 'finished'
            job.result = res.result
        else
            job.status = 'failed'
        end
    else
        job.status = 'waiting'
    end
end

local keys = redis.call('KEYS', 'coog:job:*')
for _, key in ipairs(keys) do
    local job = cjson.decode(redis.call('GET', key))
    key = key:sub(10)
    fill_status(key, job)
    if is_eligible(job) then
        insert_job(key, job)
    end
end

return result
