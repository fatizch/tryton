--[[

Description: list rq jobs in Redis (this script executes inside redis)
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
local header = {'task', 'job', 'enqueued', 'ended', 'status', 'connect',
'treat', 'ids' , 'extra'}
table.insert(result, table.concat(header, '\t'))

local function insert_job(key)
    -- retrieve data and fill o object
    local o = {job=key:sub(8)}
    o.status = redis.call('HGET', key, 'status')
    o.enqueued = redis.call('HGET', key, 'enqueued_at')
    o.ended = redis.call('HGET', key, 'ended_at') or '-'
    local desc = redis.call('HGET', key, 'description')
    local i = desc:find('%(')
    desc = desc:sub(i + 1, #desc - 1)
    desc = desc:gsub("'", '"')
    desc = cjson.decode('[' .. desc .. ']')
    o.task = desc[1]
    o.ids = table.concat(desc[2], ',')
    o.connect = desc[3]
    o.treat = desc[4]
    o.extra = table.concat(desc[5], ' ')
    -- format raw according to header
    local item = {}
    for _, k in ipairs(header) do
        table.insert(item, o[k])
    end
    table.insert(result, table.concat(item, '\t'))
end

local function is_eligible(key)
    local q
    local st
    if queue then
        q = redis.call('HGET', key, 'origin')
    end
    if check_status then
        st = redis.call('HGET', key, 'status')
    end
    return (queue == nil or q == queue) and (not check_status or
    status[st] ~= nil)
end

local keys = redis.call('KEYS', 'rq:job:*')
for _, key in ipairs(keys) do
    if is_eligible(key) then
        insert_job(key)
    end
end

return result
