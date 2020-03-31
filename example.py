from .models import Task, Project, FileModel, FileLinkModel
from .serializers import TaskSerializer
from rest_framework import permissions
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.conf import settings
from django.conf.urls.static import static
from .forms import AddTaskForm, UserRegistrationForm, AddProjectForm, AddFileForm, AddFileLinkForm, AddUserForm
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import AutoField
from json import dumps
from django.core import serializers
from wsgiref.util import FileWrapper
from django.contrib.auth import authenticate, logout, login
from django import forms
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import mimetypes
import os


"""
Регистрация
Открывается по адресу /register
При GET:
    Отдает страницу регистрации
При POST:
    Проверяет введенные данные
    Если все правильно:
        Добавляет юзера в базу
        Авторизует юзера
        Отдает редирект на страницу с проектами
    Если что-то неверно:
        Отдает страницу регистрации с предупреждениями
"""
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            userObj = form.cleaned_data
            username = userObj['username']
            email = userObj['email']
            password = userObj['password']
            if not (User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists()):
                User.objects.create_user(username, email, password)
                user = authenticate(username=username, password=password)
                login(request, user)
                return redirect('/tasks')
            else:
                raise forms.ValidationError(
                    'Looks like a username with that email or password already exists')
    return render(request, 'authorization.html', {'form': UserRegistrationForm})


"""
Авторизация
Открывается по адресу /login
При GET:
    Отдает страницу авторизации
При POST:
    Проверяет введенные данные
    Если все правильно:
        Авторизует юзера
        Отдает редирект на страницу с проектами
    Если что-то неверно:
        Отдает страницу авторизации с предупреждениями
"""
def zalogin(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            userObj = form.cleaned_data
            username = userObj['username']
            email = userObj['email']
            password = userObj['password']
            user = authenticate(username=username, password=password)
            try:
                login(request, user)
                return redirect('/tasks')
            except AttributeError:
                return redirect('/login')
    return render(request, 'authorization.html', {'form': UserRegistrationForm})


"""
Деавторизация
Открывается по адресу /logout
При любом запросе:
    Деавторизует пользователя
    Отдает редирект на главную страницу
"""
def nulogout(request):
    logout(request)
    return redirect('/tasks')


"""
Получение пользователя
Параметры:
    request - объект запроса
    user_id - идентификатор пользователя / integer
Если user_id не задан - берет его из request
Если пользователь существует:
    Отдает объект User с нужным id
Иначе отдает None
"""
def get_user(request, user_id=None):
    if user_id is None:
        user_id = request.user.id
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


"""
Проверка авторизации
Параметры:
    request - объект запроса
Отдает значение аутентификации
"""
def is_auth(request):
    return request.user.is_authenticated


"""
Проверка прав доступа юзера в проекте
Параметры:
    user - объект пользователя / User
    project_id - идентификатор проекта / integer
При несуществующем проекте, либо при отсутствии прав доступа отдает False
Иначе отдает True
"""
def check_project(user, project_id):
    if project_id is None:
        return False
    elif user.project_set.filter(id=project_id).count() == 0:
        return False
    return True


"""
Проверка существования пользователя
Параметры:
    username - имя пользователя / string
При не заданном username, либо при несуществующем пользователе отдает False
Иначе отдает True
"""
def check_user(username):
    if username is None:
        return False
    elif User.objects.get(username=username) is None:
        return False
    return True


"""
Добавление юзера
Еще не открывается ни по какому адресу
При GET:
    Отдает строку о том, что адрес недоступен с данным типом запроса
При POST:
    Проверяет значение формы, существование пользователя и права его доступа к проекту
    Если все правильно:
        Добавляет юзера в поле БД заданного проекта
    Отдает JSON вида:
    {
        'status': boolean
    }
"""
def add_user(request):
    data = {
        'status': False
    }
    if request.method == 'POST':
        auf = AddUserForm(request.POST)
        if auf.is_valid() and check_project(request.user, request.GET.get("id")) and check_user(request.GET.get("username")):
            author = auf.save()
            author.project = Project.objects.get(id=request.GET["id"])
            author.Project.add(User.objects.get(username=request.GET["username"]))
            author.save()
            data["status"] = True
        return HttpResponse(dumps(data))
    return HttpResponse("This URL shouldn't be accessed with web browser")


"""
Главная страница
Открывается по адресу /
Если юзер авторизован:
    Получаем список его проектов
Отдает главную страницу, передавая при этом:
    Форму добавления проекта
    Форму добавления пользователя в проект
    Список проектов пользователя 
"""
@csrf_exempt
def index(request):
    projects = []
    if is_auth(request):
        projects = request.user.project_set.all()[::1]
        return render(
            request,
            "projects.html",
            {
                "projform": AddProjectForm,
                "projects": projects,
                "user": get_user(request)
            }
        )
    return render(
        request,
        "index.html"
    )


"""
Страница проекта
Открывается по адресу /project
Требуется авторизация
При отсутствии проекта отдает редирект на главную страницу
При POST:
    Проверяет FileForm и FileLinkForm
    Если все правильно - сохраняет в БД и ФС
Получает список файлав
Получает список файлов-ссылок
Отдает страницу проекта вместе с:
    Формой добавления карточки
    Списком файлов
    Списком файлов-ссылок
    Идентификатором проекта
"""
@login_required
@csrf_exempt
def project(request):
    if not check_project(request.user, request.GET.get("id")):
        return redirect('index')
    project = Project.objects.get(id=request.GET.get("id"))
    return render(
        request,
        "project.html",
        {
            "form": AddTaskForm(),
            "project": project
        }
    )


"""
Добавление нового проекта
Открывается по адресу /add_project
Требуется авторизация
При POST:
    Проверяет форму AddProjectForm
    Если все хорошо:
        Записывает в БД
Отдает JSON вида:
{
    'status': boolean
}
"""
@login_required
def add_project(request):
    data = {
        'status': False
    }
    if request.method == 'POST':
        projectform = AddProjectForm(request.POST)
        if projectform.is_valid():
            project = projectform.save()
            project.save()
            project.authors.add(request.user)
            data['status'] = True
    return HttpResponse(dumps(data))


"""
Получение списка карточек
Открывается по адресу /get_tasks
При POST:
    При пройденной валидации юзера и проекта:
        Получает список объектов Task с нужным идентификатором проекта
        Записывает список задач в объект ответа
    Отдает JSON вида:
        {
            'status': boolean,
            'response': list[Task]
        }
При GET:
    Отдает надпись о запрете доступа по GET
"""
@csrf_exempt
def get_tasks(request):
    data = {
        'status': False,
        'response': ''
    }
    if request.method == "POST":
        if check_project(request.user, request.GET.get("id")):
            q = Task.objects.filter(project_id=request.GET["id"])
            data['response'] = serializers.serialize('json', q)
            data['status'] = True
        return HttpResponse(dumps(data))
    return HttpResponse("This URL shouldn't be accessed with web browser")


"""
Добавление новой карточки
Открывается по адресу /add_task
При POST:
    Валидирует форму AddTaskForm
    Проверяет доступ юзера и существование проекта
    Если все правильно:
        Сохраняет карточку в БД
    Отдает JSON вида:
        {
            'status': boolean
        }
При GET:
    Отдает надпись о запрете доступа по GET
"""
@csrf_exempt
def add_task(request):
    data = {
        'status': False
    }
    if request.method == 'POST':
        taskform = AddTaskForm(request.POST)
        if taskform.is_valid() and check_project(request.user, request.GET.get("id")):
            task = taskform.save()
            task.project = Project.objects.get(id=request.GET["id"])
            task.save()
            data["status"] = True
        return HttpResponse(dumps(data))
    return HttpResponse("This URL shouldn't be accessed with web browser")


"""
Удаление карточки
Открывается по адресу /delete_task
При POST:
    Проверяет права доступа, существование проекта и карточки
    Если все правильно:
        Удаляет карточку из БД
    Отдает JSON вида:
        {
            'status': boolean
        }
При GET:
    Отдает надпись о запрете доступа по GET
"""
@csrf_exempt
def delete_task(request):
    data = {
        'status': False
    }
    if request.method == 'POST':
        if request.GET.get("id") is not None:
            task = Task.objects.get(id=request.GET.get("id"))
            if check_project(request.user, task.project.id):
                task.delete()
                data["status"] = True
        return HttpResponse(dumps(data))
    return HttpResponse("This URL shouldn't be accessed with web browser")


"""
Редактирование карточки
Открывается по адресу /update
При POST:
    Получает карточку
    Проверяет существование проекта и права юзера
    Если все правильно:
        Заменяет заголовок карточки на указанный в запросе
        Сохраняет в БД
    Отдает JSON вида:
        {
            'status': boolean
        }
При GET:
    Отдает надпись о запрете доступа по GET
"""
@csrf_exempt
def edit_task(request):
    data = {
        'status': False
    }
    if request.method == 'POST':
        if request.POST.get("id") is not None:
            task = Task.objects.get(id=request.POST['id'])
            if task is not None and check_project(request.user, task.project.id):
                task.title = request.POST['title']
                task.notes = request.POST['notes']
                task.status = request.POST['status']
                task.priority = request.POST['priority']
                task.save()
                data["status"] = True
        return HttpResponse(dumps(data))
    return HttpResponse("This URL shouldn't be accessed with web browser")


"""
Удаление файла
Открывается по адресу /delete_file
Проверяет наличие проекта, файла и прав доступа юзера
Если type задан как file:
    Находит объект FileModel
    Удаляет файл из ФС
    Удаляет объект из БД
Если type задан как link:
    Находит объект FileLinkModel
    Удаляет объект из БД
Отдает редирект на страницу проекта
"""
@csrf_exempt
def delete_file(request):
    if check_project(request.user, request.GET.get("id")) and request.GET.get("file_id") is not None:
        if request.GET.get("type") == "file":
            file_ = FileModel.objects.get(id=request.GET["file_id"])
            file_.file.delete(False)
            file_.delete()
        if request.GET.get("type") == "link":
            filelink = FileLinkModel.objects.get(id=request.GET["file_id"])
            filelink.delete()
        return redirect("/project_docs?id={}".format(request.GET.get("id")))
    return redirect("index")


"""
Страница документов проекта
Открывается по адресу /project_docs
Если у юзера нет прав доступа:
    Отдает редирект на главную страницу
При POST:
    Проверяет формы FileForm и FileLinkForm
    Сохраняет файлы в БД и ФС если все ок
Получает список файлов и файлов-ссылок
Отдает страницу документов проекта и с ней:
    Форму добавления файла
    Форму добавления файла-ссылки
    Список файлов
    Список файлов-ссылок
    Идентификатор проекта
"""
@login_required
def project_docs(request):
    if not check_project(request.user, request.GET.get("id")):
        return redirect('index')
    if request.method == 'POST':
        fileform = AddFileForm(request.POST, request.FILES)
        if fileform.is_valid():
            file_ = fileform.save()
            file_.project = Project.objects.get(id=request.GET["id"])
            file_.save()
        filelinkform = AddFileLinkForm(request.POST)
        if filelinkform.is_valid():
            filelink = filelinkform.save()
            filelink.project = Project.objects.get(id=request.GET["id"])
            filelink.save()
    files = FileModel.objects.filter(project=Project.objects.get(id=request.GET["id"]))
    linkfiles = FileLinkModel.objects.filter(project=Project.objects.get(id=request.GET["id"]))
    return render(
        request,
        "docs.html",
        {
            "fileform": AddFileForm,
            "filelinkform": AddFileLinkForm,
            "files": files,
            "linkfiles": linkfiles,
            "project": Project.objects.get(id=request.GET.get("id"))
        })


"""
Скачивание файла
Открывается по адресу /download_doc
Если у юзера нет прав доступа или отсутствует один из параметров:
    Отдает редирект на главную страницу
Если type задан как link:
    Отдает редирект на ссылку внутри файла-ссылки
Если type задан как file:
    Получает путь файла
    Получает имя файла
    Считывает файл
    Собирает респонс с нужными параметрами, такими как длина файла, имя файла и т.д.
    Отдает файл на скачивание
"""
@login_required
def download_doc(request):
    if not check_project(request.user, request.GET.get("id")):
        return redirect('index')
    elif request.GET.get("type") is None or request.GET.get("file_id") is None:
        return redirect('index')
    elif request.GET['type'] == 'link':
        return redirect(FileLinkModel.objects.get(id=request.GET['file_id']).link)
    elif request.GET['type'] == 'file':
        file_path = FileModel.objects.get(id=request.GET['file_id']).file.path
        file_name = file_path.split("/")[-1] # windows: "\\"; linux: "/";
        file_wrapper = FileWrapper(open(file_path,'rb'))
        file_mimetype = mimetypes.guess_type(file_path)
        response = HttpResponse(file_wrapper, content_type=file_mimetype)
        response['X-Sendfile'] = file_path
        response['Content-Length'] = os.stat(file_path).st_size
        response['Content-Disposition'] = 'attachment; filename={}'.format(file_name)
        return response
