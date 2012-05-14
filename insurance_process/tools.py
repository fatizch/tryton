def to_list(data):
    if type(data) == list:
        return data
    elif type(data) == str:
        return [data]
    else:
        return [data]
