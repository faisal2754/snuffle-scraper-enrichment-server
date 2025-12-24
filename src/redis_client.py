import os
import logging
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TASK_RESULT_TTL = 60 * 60 * 600  # 600 hours
MIN_CONFIDENCE_SCORE = 0.5

try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
except RedisError as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
    raise

_UPDATE_AND_CHECK_TASK_LUA = """
local key = KEYS[1]
local result_json = ARGV[1]
local ttl = tonumber(ARGV[2])

local raw = redis.call('GET', key)
if not raw then
  return {err = 'NOT_FOUND'}
end

local data = cjson.decode(raw)
local result = cjson.decode(result_json)

if data.results == nil then
  data.results = {}
end

table.insert(data.results, result)
data.numTasksCompleted = (data.numTasksCompleted or 0) + 1

local just_completed = 0
if data.numTasksCompleted == data.numTasks then
  if data.status ~= 'completed' then
    data.status = 'completed'
    just_completed = 1
  end
end

redis.call('SETEX', key, ttl, cjson.encode(data))
return {data.numTasksCompleted, data.numTasks, just_completed}
"""

update_and_check_task_script = redis_client.register_script(_UPDATE_AND_CHECK_TASK_LUA)

