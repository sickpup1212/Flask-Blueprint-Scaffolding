clone the project

cd into it

create a virtual environment

source env/bin/activate

pip install -r requirements

touch .env

add your postgresql connection string to your .env file @ POSTGRESQL_CONN_STRING

go look at app/models.py

there are already three models in there you can use to test it out or you can put your own

DO NOT PUT ANY SQLALCHEMY MODEL CLASS PERTAINING TO USER AUTHENTICATION

THE USERS CLASS THAT ALREADY EXISTS HAS AUTHENTICATION SET UP ALREADY

go back to root folder (cd ..)

run scaffolding (python3 generate_scaffolding.py)

now you have created a blueprint, a form.py, a routes.py, and 5 views/endpoints create, list, edit, view, delete for each model in your app/model.py

look inside the templates folder to see the .html files and macros for each model

The users blueprint has a couple endpoints and templates that no other class will get which are:

 ---- /users/login and login.html
 
 ---- /users/register and register.html

so instead of creating users by going to /users/create you need to go to users/register

this is the first endpoint you need to go to upon first running the server successfully because everying is

@login_required protected.  Register your account, the login (both using /users/) and then you can navigate anywhere

if you have any child/parent dependant relationships the model the child model will not get a create endpoint 

instead the functionality to create the child instances will be at /{parent_model_name}/\<id\>/add-product

the \<id\> is the id of the parent instance you want to add the child too.  so you have to create a parent instances first @ /{parent_model_name}/create
