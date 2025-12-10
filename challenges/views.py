from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from .models import Challenge, ChallengeSolution, QuoteSubmission
from .forms import ChallengeForm, ChallengeSolutionForm
from services.ai_challenge import get_challenge_feedback, generate_new_challenge

@login_required
def challenge_list(request):
    """View for listing all challenges with pagination and search"""
    # Get filter parameters
    difficulty = request.GET.get('difficulty', '')
    query = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))
    
    # Get challenges from database
    challenges = Challenge.objects.filter(is_approved=True)
    
    # Apply difficulty filter if specified
    if difficulty:
        challenges = challenges.filter(difficulty=difficulty)
    
    # Apply search query if provided
    if query:
        challenges = challenges.filter(
            models.Q(title__icontains=query) | 
            models.Q(description__icontains=query) |
            models.Q(created_by__username__icontains=query)
        )
    
    # Order challenges by creation date (newest first)
    challenges = challenges.order_by('-created_at')
    
    # Pagination
    items_per_page = 6
    total_challenges = challenges.count()
    total_pages = (total_challenges + items_per_page - 1) // items_per_page
    
    # Handle page boundaries
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # Get current page items
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    current_challenges = challenges[start_index:end_index]
    
    # Check if user has already submitted solutions for these challenges
    if request.user.is_authenticated:
        challenge_ids = [challenge.id for challenge in current_challenges]
        user_solutions = {}
        solutions = ChallengeSolution.objects.filter(
            challenge_id__in=challenge_ids,
            user=request.user
        )
        for solution in solutions:
            user_solutions[solution.challenge_id] = solution
    else:
        user_solutions = {}
    
    context = {
        'challenges': current_challenges,
        'difficulty_filter': difficulty,
        'query': query,
        'total_challenges': total_challenges,
        'total_pages': total_pages,
        'current_page': page,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'page_range': range(max(1, page - 2), min(total_pages + 1, page + 3)),
        'user_solutions': user_solutions,
    }
    
    return render(request, 'challenges/view_challenges.html', context)

@login_required
def challenge_detail(request, pk):
    """View for displaying a single challenge"""
    challenge = get_object_or_404(Challenge, pk=pk, is_approved=True)
    
    # Check if user has already submitted a solution
    user_solution = None
    if request.user.is_authenticated:
        user_solution = ChallengeSolution.objects.filter(
            challenge=challenge,
            user=request.user
        ).order_by('-submitted_at').first()
    
    # Create solution form
    form = ChallengeSolutionForm()
    
    context = {
        'challenge': challenge,
        'user_solution': user_solution,
        'form': form,
    }
    
    return render(request, 'challenges/challenge_detail.html', context)

@login_required
def create_challenge(request):
    """View for creating a new challenge"""
    if request.method == 'POST':
        form = ChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save(commit=False)
            challenge.created_by = request.user
            challenge.is_approved = True
            challenge.save()
            
            messages.success(request, "Your challenge has been created!")
            return redirect('challenge_detail', pk=challenge.pk)
    else:
        form = ChallengeForm()
    
    return render(request, 'challenges/create_challenge.html', {'form': form})

@login_required
def quote_list(request):
    """View for listing quotes (temporary until quotes are integrated with dashboard)"""
    # For now, just redirect to dashboard
    return render(request, 'dashboard/dashboard.html')

@login_required
def submit_solution(request, pk):
    """Submit a solution to a challenge and get AI feedback"""
    challenge = get_object_or_404(Challenge, pk=pk, is_approved=True)
    
    if request.method == 'POST':
        form = ChallengeSolutionForm(request.POST)
        if form.is_valid():
            try:
                # Create the solution object
                solution = form.save(commit=False)
                solution.challenge = challenge
                solution.user = request.user
                solution.is_correct = True  # Mark all submitted solutions as correct for now
                # Check if correctness_level column exists and set it
                try:
                    solution.correctness_level = 'correct'  # Set correctness level to 'correct' by default
                except Exception as e:
                    print(f"Error setting correctness_level: {e}")
                    # Field might not exist yet, continue anyway
                
                # Get AI feedback
                try:
                    print(f"Getting AI feedback for challenge solution: {solution.solution_text[:100]}...")
                    solution.ai_feedback = get_challenge_feedback(
                        solution.solution_text, 
                        challenge, 
                        request.user.username
                    )
                    print(f"Received AI feedback: {solution.ai_feedback[:100]}...")
                except Exception as e:
                    print(f"Error getting AI feedback: {e}")
                    solution.ai_feedback = f"Our AI assistant is taking a break, but your solution shows real effort, {request.user.username}! Keep exploring different approaches and don't give up."
                
                solution.save()
                messages.success(request, "Your solution has been submitted! Check out the AI feedback.")
            except Exception as e:
                print(f"Error saving solution: {e}")
                messages.error(request, "There was an error saving your solution. Please try again.")
        else:
            messages.error(request, "Please correct the errors in the form.")
    
    return redirect('challenge_detail', pk=pk)

@login_required
def generate_ai_challenge(request):
    """Generate a challenge using AI"""
    if request.method == 'POST':
        difficulty = request.POST.get('difficulty', 'beginner')
        topic = request.POST.get('topic', 'programming')
        
        try:
            # # Get AI-generated challenge
            # challenge_text = generate_new_challenge(difficulty, topic, request.user.username)
            
            # # Parse the response with improved structured parsing
            # lines = challenge_text.strip().split('\n')
            result = generate_new_challenge(difficulty, topic, request.user.username)
            challenge_text = result["raw"]
            ai_hints = [result["hints"].get(f"hint_{i}") for i in range(1, 4)]
            # Extract title and description from the raw text
            title = ""
            description = ""
            lines = challenge_text.strip().split('\n')
            current_section = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                    current_section = "title"
                elif line.startswith("DESCRIPTION:"):
                    current_section = "description"
                elif current_section == "description" and not line.startswith("HINT"):
                    description += line + "\n"
            # Ensure we have exactly 3 hints with quality fallbacks
            default_hints = [
                "Start by breaking down the problem into smaller parts. What's the first step you would take?",
                "Consider edge cases and how your solution handles different inputs. What assumptions are you making?",
                "Look at your algorithm's efficiency. Can you optimize it further? Remember to test your solution with various inputs."
            ]
            hints = []
            for i in range(3):
                if ai_hints[i] and ai_hints[i].strip():
                    hints.append(ai_hints[i].strip())
                else:
                    hints.append(default_hints[i])
            # Create the challenge
            challenge = Challenge(
                title=title if title else "AI Generated Challenge",
                description=description.strip(),
                difficulty=difficulty,
                hints=hints,
                created_by=request.user,
                is_ai_generated=True,
                is_approved=True  # Auto-approve AI challenges
            )
            challenge.save()
            
            messages.success(request, "Your AI challenge has been generated!")
            return redirect('challenge_detail', pk=challenge.pk)
        except Exception as e:
            print(f"Error generating AI challenge: {e}")
            messages.error(request, "There was an error generating your challenge. Please try again.")
    
    return render(request, 'challenges/generate_challenge.html')