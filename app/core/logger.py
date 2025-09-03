import json, logging, sys


logger = logging.getLogger("pms")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_json(level: str, **kwargs):
    msg = json.dumps(kwargs, ensure_ascii=False)
    getattr(logger, level.lower(), logger.info)(msg)