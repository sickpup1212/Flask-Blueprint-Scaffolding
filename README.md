# Flask-Blueprint-Scaffold

**git clone https://github.com/sickpup1212/Flask-Blueprint-Scaffolding.git**

**cd Flask-Blueprint-Scaffolding**

**python3 -m venv env**

**source env/bin/activate**

**pip install -r requirements**

**echo 'POSTGRESQL_CONN_STRING={your_postgres_connection_string)' >> .env**

## your Flask-SQLAlchemy models dictate the build out

**cat app/models.py**

### !!!! **when using your models instead of the default rememeber** !!!!

  1. ***DO NOT*** ADD ANY CLASSES/MODELS PERTAINING TO USER AUTHENTICATION
  
  2. **DO NOT** ADD ANY CLASSES/MODELS called 'User'
  
  3. **DO** USE THE MODEL/CLASS THAT ALREADY EXISTS CALLED 'User' (\_\_tablename\_\_ 'users')
  
  4. **THIS User Class** will not appear in app/models.py until **AFTER** the scaffold has been run.

  5.  **DO** make each of your model/classes a singular name (Product, or Client)
  6.  **DO** make your \_\_tablename\_\_ the pluralized version (products, clients)
  7.  **REMEMBER THAT**

      1.bp_name

      2.model_table_name,

      3.\_\_tablename\_\_ and

      4.blueprint_name

      are **all** refering to the same thing: the lower case and pluralized versions of your singluar named model/class

      -- **example** -- class/singular: **Product** table/plural: **products**

**cd ..**

**python3 generate_scaffolding.py**

## for EVERY MODEL definition in app/models.py

### You Get:

   - a ***blueprint diretory*** containing:
     
   - a **form.py** with forms made from your model
     
   - a **routes.py** with:

     - 5 views/endpoints:
       
         - create
           
         - list
           
         - edit
           
         - view
           
         - delete

### You Must:

   - **ADD**:
     
     **'from {bp_name} import {bp_name}_bp'**
     
     and
     
     **'app.blueprint_register({bp_name}_bp)'**
     
     to **app/app.py** inside the **create_app** function.

## Start Server

**python3 app/app.py** from your root directory 

or

**python3 app.py** from app/

.html files and macros in templates/{bp_name}

### The **users** blueprint has a couple **endpoints** and **templates** that no other class will get which are:

 ---- **/users/login** and **login.html**
 
 ---- **/users/register** and **register.html**

**DO NOT** create users by going to **users/create**

**DO** create users by going to **users/register**

Most routes are **@login_required** protected 

**users/register** and **users/login** are not protected.  

users MUST **register** and **login** to be able to do/see anything

# IMPORTANT

## CHILD PARENT RELATIONSHIPS

When using a child/parent relationship in your model, the child model will not get a **/create** endpoint 

Instead of **/create** you can use **/{parent_model_name}/\<id\>/add-{child_name_lowercase_and_singular}** AFTER you create at least one instance of the parent. 

   - example: **clients/1/add-product** if your classes are **Client** and **Product** and respective **\_\_tablenames\_\_** are **'clients'** and **'products'** 

   - the **\<id\>** is the id of the parent instance.  the default is they increment serially from 1, **1 being the first instance**.

   - So in order to add a **product** to your 5th **client** the **endpoint** would look like **clients/5/add-product**.
