from flask import Flask,render_template,request,jsonify
import subprocess
import os 
import tempfile 


app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/execute',methods=['POST','GET'])
def code_editor():
    language = request.form.get('language')
    code = request.form.get('code')
    
    with tempfile.NamedTemporaryFile(delete=False,suffix=f'.py') as temp_file:
        temp_file.write(code.encode())
        tempfile_path = temp_file.name
    
    output=''
    try:
        output = subprocess.check_output(['python',tempfile_path],stderr=subprocess.STDOUT).decode()
    
    except subprocess.CalledProcessError as e:
        output = e.output.decode() if e.output else str(e)
        
    finally:
        # clean up the temp files
        os.remove(tempfile_path)
    
    return jsonify({'output':output})
    

if __name__ == '__main__':
    app.run(debug=True)