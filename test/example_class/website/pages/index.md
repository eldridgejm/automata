<div class="row">
    <div class="col-md-12 p-2">
        <img class="d-block mx-auto mx-md-0" src="static/logo.svg">
    </div>
</div>

<div style="margin-top: 3em; margin-bottom: 3em; padding: 0em">
{{ elements.button_bar(config['buttons']['top']) }}
{{ elements.button_bar(config['buttons']['bottom']) }}
</div>

Welcome to {{ context.course.name }}.

{{ elements.schedule(config['schedule']) }}
