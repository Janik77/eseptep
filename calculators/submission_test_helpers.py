"""Exercise the rendered-result token in existing persistence integration tests."""
def post_result(client, url, data, **kwargs):
    if isinstance(data, dict) and data.get('action') in {'save_estimate', 'request_master', 'request_supplier'}:
        preview = client.post(url, {k: v for k, v in data.items() if k != 'action'})
        if preview.context and preview.context.get('submission_token'):
            data = {**data, 'submission_token': preview.context['submission_token']}
    return client.post(url, data, **kwargs)
