from routeros_api import RouterOsApiPool
api_pool = RouterOsApiPool('192.168.88.1', 'homemonitor', 'foxpass', port=8728, plaintext_login=True)
api = api_pool.get_api()
print(api.get_resource('/system/identity').get())
api_pool.disconnect()