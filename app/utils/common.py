import random
import string
import time


def rand_str(length=16, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(length))


def get_timestamp():
    return int(time.time() * 1000)
