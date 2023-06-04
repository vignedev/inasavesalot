const $ = document.querySelector.bind(document)

window.onload = async e => {
	const playerContainer = $('.player')
	const select = $('select')

	const
		last_save = $('#last_save'),
		next_save = $('#next_save'),
		save_count = $('#save_count'),
		save_count_header = $('#save_header'),
		random_msg = $('#random')

	let data = null
	let currentVideo = null
	let player = null

	// random messages, as per usual
	const messages = [
		'no longer bash-ing this',
		'wait is that the sun rising',
		'no i havent slept yet',
		'my laptop fans died',
		'no i didnt remove pc fans to keep it quiet',
		'pure js and html, delightful',
		'ina is very cute',
		'wait where\'s the faq',
		'haphazardly ducttaped together' // in 6 hours
	]
	random_msg.innerText = messages[Math.floor(Math.random() * messages.length)]

	// load data
	try{ data = await (await fetch('assets/videos.json')).json() }
	catch(err){
		select.innerHTML = '<option disabled selected>oh nyo, i broke</option>'
		console.error(err)
		return
	}

	let index = 0, counter = 0
	for(const videoId in data){
		// update the selects to add the videos
		const option = document.createElement('option')
		option.value = videoId
		option.innerText = data[videoId].title
		select.append(option)

		// also convert the times to seconds
		data[videoId].saves = data[videoId].saves.map(x => x / 30.0)
		data[videoId].index = index++
		data[videoId].start = counter
		counter += data[videoId].saves.length
	}
	select.disabled = false
	select.onchange = e => load_video(e.target.value)

	// if hash is present, then try to load it
	const hashId = location.hash.substr(1)
	if(data[hashId]){
		select.value = hashId
		load_video(hashId)
	}

	function lowerBound(value, array) {
		let low = 0;
		let high = array.length;

		while (low < high) {
			const mid = Math.floor((low + high) / 2);

			if (array[mid] < value) {
			  low = mid + 1;
			} else {
			  high = mid;
			}
		}

		return [ low, array[low] ];
	}

	setInterval(update_stats, 500) // check every half a second, we don't need maximum precision

	function get_wordy_time(seconds){
		// this is garbage, but it is... fixed hehe
		if(seconds < 60) {
			const n = seconds.toFixed(0)
			return `${n == '1' ? 'a' : n} second${n == '1' ? '' : 's'}`
		}
		if(seconds >= 60 && seconds < 3600){
			const n = (seconds / 60).toFixed(0)
			return `${n == '1' ? 'a' : n} minute${n == '1' ? '' : 's'}`
		}
		const n = (seconds / 3600).toFixed(0)
		return `${n == '1' ? 'an' : n} hour${n == '1' ? '' : 's'}`
	}

	function update_stats(){
		const info = data[currentVideo]
		if(!info || player == null || !player.getCurrentTime) return

		let newly_added = 0
		if(info.saves.length == 0){ // special case for that one time ina did not save
			last_save.innerText = 'last stream'
			next_save.innerText = 'next stream'
		}else{
			const currentTime = player.getCurrentTime()
			const [ index, closest ] = lowerBound(currentTime, info.saves)

			if(index == 0){ // first item
				last_save.innerText = info.index == 0 ? 'never' : 'last stream'
				next_save.innerText = `${get_wordy_time(closest - currentTime)}`
			}else if(index == info.saves.length){ // last item
				last_save.innerText = `${get_wordy_time(currentTime - info.saves[index-1])} ago`
				next_save.innerText = 'next stream'
				newly_added = index
			}else{ // middle
				last_save.innerText = `${get_wordy_time(currentTime - info.saves[index-1])} ago`
				next_save.innerText = `${get_wordy_time(info.saves[index] - currentTime)}`
				newly_added = index
			}
		}
		const total = info.start + newly_added
		save_count.innerText = `${total} time${total == 1 ? '' : 's'}`

		if(player.getPlayerState() == 5){
			save_count_header.innerText = `TOTAL SAVES`
			const total = info.start + info.saves.length
			save_count.innerText = `${total} time${total == 1 ? '' : 's'}`
		}else{
			save_count_header.innerText = `CURRENTLY SAVED`
		}
	}

	async function load_video(videoId){
		// calculate the previous, current etc. 
		const info = data[videoId]
		if(!info) return false

		currentVideo = videoId
		last_save.innerText = next_save.innerText = save_count.innerText = '...'

		// recreate the player
		if(player) player.destroy()
		player = new YT.Player('video', {
			width: 1280, height: 720, videoId: videoId, events: {
				onReady: e => { update_stats() },
				onStateChange: e => { update_stats() }
			},
			playerVars: {
				playsinline: 1
			}
		})
		window.location.hash = videoId
	}
}
