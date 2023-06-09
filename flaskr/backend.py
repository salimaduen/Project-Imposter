from hashlib import sha256
from google.cloud import storage
from flask_login import current_user
from flaskr.user import User
import base64
import json
from datetime import datetime, timedelta

# TODO(Project 1): Implement Backend according to the requirements.
class Backend:

    def __init__(self):
        # Starts class instance with a Storage Client
        self.storage_client = storage.Client(project="snappy-premise-377919")

    def _get_content_bucket(self):
        # Function returns content bucket
        return self.storage_client.bucket("sus-wiki-content-bucket")

    def _get_userpass_bucket(self):
        # Function returns user/pass bucket
        return self.storage_client.bucket("sus-user-pass-bucket")
        
    def get_wiki_page(self, name):

        # Get content bucket object
        content_bucket = self._get_content_bucket()

        # Retrieves page from bucket
        page_blob = content_bucket.blob("pages/" + name)

        # If it does not exist return nothing
        if not page_blob.exists():
            return None

        page_content = None
        # Reads blob object content and writes it to page_content variable
        with page_blob.open('r') as f:
            page_content = f.read()

        return page_content

    def get_author(self, name):
        # Function for getting an author

        # Content Bucket instance
        content_bucket = self._get_content_bucket()

        # Retrieves blob by author
        author_blob = content_bucket.blob("author/" + name)

        # Nothing returned if it does not exist
        if not author_blob.exists():
            return None

        author_content = None

        # Reads content of blob
        with author_blob.open('r') as f:
            author_content = f.read()
        return author_content

    def get_all_page_names(self):

        # Initialize an empty list for the pages names
        names = []

        # For loop iterates through content bucket blob objects/pages
        for blob in self.storage_client.list_blobs(self._get_content_bucket(),
                                                   prefix="pages/"):

            # Appends them to the list
            name = blob.name[len("pages/"):]
            names.append(name)

        # List is returned
        return names

    #Returns a dictionary containing the categories data
    def get_categories(self):
        categories = dict()
        
        content_bucket = self._get_content_bucket()
        categories_blob = content_bucket.blob("categories/categories.csv")

        """
        Categories are harcoded in a CSV formatted as follows: 
        <Category name>,<page1>,<page2>,<page3>
        <Category name>,<page1>
        """
        #Opening the blob as a file, convert each line into one key/value pair
        with categories_blob.open('r') as file:
            lines = file.readlines()
            
            for line in lines:
                currCategory = [value.strip() for value in line.split(",")]
                
                #Key is the first value, values is the rest
                key = currCategory[0]
                values = set(currCategory[1:])             
                categories[key] = values   

        return categories

    def save_categories(self, categories):

        #categories is a dictionary containing category data
        content_bucket = self._get_content_bucket()
        categories_blob = content_bucket.blob("categories/categories.csv")


        #"Crewmate,Crewmate,Tasks,Emergency Meeting\nImposter,Emergency Meeting,Kill,Sabotage,Sus,Venting\nTask,Tasks\nLocation,Security,Emergency Meeting\nTerminology,Sus,Venting\n"
        """
        categories = {
            "Crewmate" : {"Crewmate", "Tasks", "Emergency Meeting"},
            "Imposter" : {"Emergency Meeting", "Kill", "Sabotage", "Sus", "Venting"},
            "Tasks"    : {"Tasks"},
            "Location" : {"Security", "Emergency Meeting"},
            "Terminology" : {"Sus", "Venting"}
        }
        """

        with categories_blob.open('w') as file:
            for key, values in categories.items():
                values_string = ','.join(str(value) for value in values)
                file.write(f"{key},{values_string}\n")

        return 

    #Given a set of categories selected by user, generate all pages that are in ALL the selected. 
    def filter_categories(self, user_categories):
        #None selected, return everthing
        
        if not user_categories: 
            return self.get_all_page_names()
        categories = self.get_categories()
        filtered_pages = categories[user_categories[0]] 
        for user_category in user_categories:
            category_pages = categories[user_category]
            filtered_pages = filtered_pages.intersection(category_pages)

        return filtered_pages


    #post_image is already in base64
    def upload(self, post_title, post_content, post_image, categories):

        if categories:
            self.update_categories(post_title, categories)

        # Object from content bucket
        content_bucket = self._get_content_bucket()

        # Creates blob with the name and specific path
        the_blob = content_bucket.blob("pages/" + post_title)

        # Writes content to blob
        with the_blob.open('w') as f:
            f.write(post_content)

        # Object from image bucket
        image_bucket = self.storage_client.bucket('sus-wiki-images')

        # Create blob for image with specified name
        image_blob = image_bucket.blob(post_title)

        # Write image to blob (B64 FORMAT)
        with image_blob.open('wb') as f:
            f.write(post_image)

        # Creates author blob based on post title
        author_blob = content_bucket.blob("author/" + post_title)

        # Writes author username to blob
        with author_blob.open('w') as f:
            f.write(current_user.username)

        return post_title

    def update_categories(self, post_title, new_post_categories):
        # new_post_categories includes the categories that were selected on the website and passed to the backend.

        # Get the existing dictionary of categories with their corresponding posts.
        categories_dictionary = self.get_categories()

        # Iterate through the list of categories the user specified.
        # The post will be added to the existing category dictionary
        for category in new_post_categories:
            categories_dictionary[category].add(post_title)
        
        # Method for updating CSV file
        self.save_categories(categories_dictionary)

    #Grab image from blob (already in b64)
    #return decoded image
    def get_image(self, image_name):

        # Object from images bucket
        bucket = self.storage_client.bucket('sus-wiki-images')

        # Blob with the specified image name
        blob = bucket.blob(image_name)
        image = None

        # Opens blob and reads the content from the image (Already in B64).
        # Content is written to image variable.
        with blob.open('rb') as f:
            image = f.read()

        # Image content returned in decoded format
        return image.decode('utf-8')

    #SIGN_UP BUCKET | username is not case sensitive
    def sign_up(self, username, password, sha256=sha256):

        # Check if username and password are valid characters.
        # If not, it will return.
        if not self._check_valid(username, password):
            return 'INVALID'

        # Object from user/pass bucket.
        bucket = self._get_userpass_bucket()

        # Blob object with the specified username
        blob = bucket.blob(username.lower())

        # Checks if blob/username already exists.
        # In case it does, it will return.
        if blob.exists():
            return 'ALREADY EXISTS'

        # Password is hashed (SHA256) with 'sus' prefix + password | password = 123 -> sus123
        # This hashed password is then written into the blob.
        with blob.open('w') as f:
            prefixed_password = ''.join(['sus', password])
            f.write(sha256(prefixed_password.encode()).hexdigest())

    def sign_in(self, username, password, sha256=sha256):  # Draft for SIGN IN

        # Object from user/pass bucket
        bucket = self._get_userpass_bucket()

        # Blob object from the specified username
        blob = bucket.blob(username.lower())

        # If user does not exist it will return.
        if not blob.exists():
            return False

        # Prefix (sus) will be added to the password enter by the user.
        # Password will then be hashed (SHA256)
        prefixed_password = ''.join(['sus', password])
        hashed_password = sha256(prefixed_password.encode()).hexdigest()
        password_matches = False

        # Open blob object and read its content. ( Hashed password )
        # Comparison between the entered password and one in record is made
        with blob.open('r') as f:
            user_password = f.read()
            if hashed_password == user_password:
                password_matches = True
                f.close()

        return password_matches  # Will True if password correct -- False if not

    def _check_valid(self, username, password):

        # Function will verify if the username or password are a-z / A-Z , 0-9
        # or accepted special characters or has no spaces

        # Length of username 5 characters or more.
        # Password 8 characters or more.
        if len(username) < 5 or len(password) < 8:
            return False

        # username is not cAsE SeNsITiVe
        # Backend will always make it lowercase
        username = username.lower()

        valid_username = False
        valid_password = False

        for character in username:
            ascii_value = ord(character)

            if (int(ascii_value) >= 48 and int(ascii_value) <= 57) or (
                    int(ascii_value) >= 97 and
                    int(ascii_value) <= 122):  # a-z , 0-9
                valid_username = True

            elif int(ascii_value) == 45 or int(
                    ascii_value) == 95:  # Dash or underscore ( '_', '-' )
                valid_username = True

            else:
                valid_username = False
                break

        for character in password:

            valid_password = False
            ascii_value = ord(character)

            if (int(ascii_value) >= 48 and int(ascii_value) <= 57) or (
                    int(ascii_value) >= 97 and
                    int(ascii_value) <= 122):  # a-z, 0-9
                valid_password = True

            elif (int(ascii_value) >= 65 and int(ascii_value) <= 90):  # A-Z
                valid_password = True

            elif (int(ascii_value) >= 33 and
                  int(ascii_value) <= 42):  # Some special characters
                valid_password = True

            elif int(ascii_value) == 45 or int(
                    ascii_value) == 95:  # Dash or underscore ( '_', '-' )
                valid_username = True

            else:
                valid_password = False
                break

        return valid_username and valid_password


    def create_message(self, message : str, sender_user : User, receiver_user : User):
        # Call sent_message for the sender
        sender_user.sent_message(message, receiver_user.username)
        # Call receive message for the receiver
        receiver_user.receive_message(message, sender_user.username)
        
    def get_user_message_list(self, user: User) -> list :
        return user.get_message_list()

    def get_user_conversation_list(self, user: User) -> list :
        return user.get_conversation_list()

    # Function just for TESTING purposes
    def test(self):

        bucket = self.storage_client.bucket("sus-user-pass-bucket")

        lst = []
        for blob in bucket.list_blobs():

            if blob.name != 'admin':

                lst.append(blob.name)

        return lst

    def page_names_sorted_by_rank(self, reverse=True):
        names = self.get_all_page_names()

        names.sort( 
                # sort by page rank
                key=lambda page_name: self.get_rank(page_name),
                # do it in reverse or not
                reverse=reverse
                )

        return names

    """
    given a post's title, return its rank
    """
    def get_rank(self, post_title):
        visit_blobs = self.storage_client.list_blobs("sus-wiki-content-bucket",
                                        prefix=f'unique30/{post_title}/')
        unique_visits_30_days = []

        for blob in visit_blobs:
            page_visit = UniquePageVisit.from_blob(blob)
            if page_visit._within_30_days(prune=True, backend=self):
                unique_visits_30_days.append(page_visit)

        return len(unique_visits_30_days)

class UniquePageVisit:
    def __init__(self, post_title, ip, date):
        self.ip = ip
        self.date = date
        self.post_title = post_title

    @staticmethod
    def on_visit_page(backend, post_title, ip):
        # check if visited past 30 days
        if not UniquePageVisit.exists_in_past_30_days(backend, post_title, ip):
            # if not then update the blob
            new_visit = UniquePageVisit(post_title, ip, datetime.now())
            new_visit.update_blob(backend)
        

    """
    If you choose to prune, you also need to set the backend parameter
    """
    def _within_30_days(self, prune=False, backend=None):
        if (self.date + timedelta(days=30)) > datetime.now():
            return True

        if prune: self._delete_blob(backend)
        return False

    """
    Returns a json version of the object that is ready to be saved to a blob.
    The json is a string.
    """
    def _encode_to_json(self):
        the_data = {
            'post_title': self.post_title,
            'ip': self.ip,
            'date': self.date.isoformat(),
        }
        return json.dumps(the_data)


    """
    Get a UniquePageVisit from a json string.
    """
    @staticmethod
    def decode_from_json(the_json):
        # This tells the json module how to decode incoming data
        def _page_visit_decoder(dct):
            return UniquePageVisit(
                post_title=dct['post_title'],
                ip=dct['ip'],
                date=datetime.fromisoformat(dct['date'])
                )

        return json.loads(the_json, object_hook=_page_visit_decoder)

    @staticmethod
    def from_blob(the_blob):
        if the_blob.exists():
            the_json = the_blob.download_as_string()
            page_visit = UniquePageVisit.decode_from_json(the_json)
            return page_visit
        return None

    """
    searches the database and returns either a corresponding UniquePageVisit or None 
    """
    @staticmethod
    def from_ip(backend, post_title, ip):
        content_bucket = backend._get_content_bucket()
        the_blob = content_bucket.blob("unique30/" + post_title + "/" + ip)
        return UniquePageVisit.from_blob(the_blob)

    """
    tries to grab from database. if it exists it returns true, else return false
    """
    @staticmethod
    def exists_in_past_30_days(backend, post_title, ip):
        page_visit = UniquePageVisit.from_ip(backend, post_title, ip)
        if page_visit != None and page_visit._within_30_days():
            return True

        return False        

    def _to_blob(self, backend):
        content_bucket = backend._get_content_bucket()
        the_blob = content_bucket.blob("unique30/" + self.post_title + "/" + self.ip)
        return the_blob

    def update_blob(self, backend):
        the_blob = self._to_blob(backend)
        with the_blob.open('w') as f:
            the_json = self._encode_to_json()
            f.write(the_json)

        return the_blob

    def _delete_blob(self, backend):
        the_blob = self._to_blob(backend)
        the_blob.delete()

    def __eq__(self, other):
        return (
            isinstance(other, UniquePageVisit) and
            self.date == other.date and
            self.ip == other.ip and
            self.post_title == other.post_title
            )
    