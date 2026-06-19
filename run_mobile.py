from flask import Flask, send_file
app = Flask(__name__)
@app.route('/')
def home():
    return send_file('mobile_app.html')
if __name__ == '__main__':
    print('=' * 50)
    print('DYNAX Mobile App')
    print('=' * 50)
    print('Open: http://127.0.0.1:6007')
    print('=' * 50)
    app.run(host='0.0.0.0', port=6007, debug=False)
