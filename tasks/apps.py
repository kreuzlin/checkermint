from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = "tasks"
    verbose_name = "Themen und Aufgaben"

    def ready(self):
        from core import private_files

        from .models import InstructionImage

        private_files.register(
            "anleitungsbild",
            private_files.PrivateFileKind(
                model=InstructionImage,
                get_file=lambda image, variant: None if variant else image.image,
                can_access=lambda user, image: image.visible_to(user),
                # Re-encoded by core.images, so it may be shown inline.
                inline=True,
                get_filename=lambda image: image.original_filename,
                # The file behind an id never changes.
                cache_control="private, max-age=86400",
            ),
        )
